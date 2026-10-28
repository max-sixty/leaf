"""Click declarations and production command wiring.

Every command speaks JSON, since agents are its only readers: its result on stdout,
one JSON value (a record per line for a write), and anything said beside it on
stderr, one JSON object per line. That is a note, a finding (`findings.note`), or a
refusal ending the command, `{"error", "findings"}` (`LeafGroup`). So a reader that
merges the streams still parses every line, one that pipes stdout alone still sees
what was said beside it, and a refusal never reads as a result. `--help`, `--version`
and `--root` print text, and `package run` prints what its script does.

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

from leaf.render_gate.browser import VARIABLES as BROWSER_VARIABLES
from leaf.schema import WAIT_BATCH_OUTPUT_INSTRUCTION
from leaf.state import EVENTS_FILE, PLUGIN_ROOT


class Reported(NamedTuple):
    """A result that also sets the exit status, as a check's report does."""

    result: dict
    status: int


def resolve_dir(dir_arg: str, *, renew: bool = True) -> Path:
    """The page a command names. A write may renew an older layer for its owning
    session (`vendoring.renew_layer`); reads and service stops leave it alone."""
    from leaf.interaction_log import acting_on

    page_dir = page_path(dir_arg)
    if page_dir.is_file():
        raise click.ClickException(
            f"{page_dir} is a file; a page command takes the page's directory"
        )
    if not (page_dir / EVENTS_FILE).is_file():
        raise click.ClickException(
            f"{page_dir} is not an initialized page; "
            f"run `leaf page init {shlex.quote(str(page_dir))}`"
        )
    acting_on(page_dir)
    if not renew:
        return page_dir
    from leaf.findings import note
    from leaf.harness import session_harness
    from leaf.vendoring import renew_layer

    if unready := renew_layer(page_dir, session_harness(), command=True):
        note(unready)
    return page_dir


def page_path(dir_arg: str) -> Path:
    """The directory a page argument spells, whether or not it holds a page yet."""
    from leaf.locations import canonical_path

    return canonical_path(Path(dir_arg).expanduser())


class _Page(click.ParamType):
    """A PAGE argument, resolved by `resolve_dir` before the command runs."""

    name = "page"

    def __init__(self, *, renew: bool):
        self.renew = renew

    def convert(self, value, param, ctx) -> Path:
        return resolve_dir(value, renew=self.renew)


def page_argument(*, renew: bool, required: bool = True):
    """Declare a command's PAGE, passed as `page_dir`, the page it names. Every
    command says whether naming the page renews its layer: a write may, while a read
    or a service stop must not renew the page it acts on."""
    return click.argument(
        "page_dir", metavar="PAGE", type=_Page(renew=renew), required=required
    )


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
    if result is None:
        return
    from leaf.event_log import jsonl_line

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
    """Print the payload directory and stop.

    `--version` identifies the source; this distinguishes a harness's installed
    plugin from a checkout of that same source.
    """
    if not value or ctx.resilient_parsing:
        return
    click.echo(PLUGIN_ROOT)
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

    group_class = type

    def resolve_command(self, ctx, args):
        name, command, remaining = super().resolve_command(ctx, args)
        # Click has resolved this path, including options before its subcommand.
        ctx.ensure_object(dict)["leaf_command"] = (
            f"{ctx.command_path} {name}".removeprefix(f"{ctx.find_root().info_name} ")
        )
        return name, command, remaining

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
        from leaf.session_runtime import hand_off_command

        hand_off_command(sys.argv[1:] if args is None else list(args))
        invocation = extra.setdefault("obj", {})
        try:
            self._run_standalone(args, prog_name, complete_var, **extra)
        finally:
            from leaf.interaction_log import record_command

            record_command(invocation.get("leaf_command", ""))

    def _run_standalone(self, args, prog_name, complete_var, **extra) -> None:
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


@cli.command(hidden=True)
@click.option("--harness", required=True)
@click.option("--if-claimed", is_flag=True, expose_value=False)
@click.option("--watch", is_flag=True)
@click.option("--pages", is_flag=True)
def hook(harness: str, watch: bool, pages: bool) -> None:
    """Answer a native harness hook from its JSON payload on stdin."""
    if watch and pages:
        raise click.UsageError("--watch and --pages are mutually exclusive")
    from leaf.hooks import main

    main(harness, watch=watch, pages=pages)


@cli.command(hidden=True)
def session_end() -> None:
    """End the harness instance named by the JSON payload on stdin."""
    from leaf.state import main

    main()


@cli.group(short_help="Launch the experimental Codex terminal.")
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


@page.command(short_help="Create a page directory or change its packages.")
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
    help="remove all explicit packages and the selected personal theme",
)
@click.option(
    "--theme", metavar="NAME", help="select a personal theme from `leaf theme list`"
)
@click.option(
    "--no-theme",
    is_flag=True,
    help="clear the personal theme while keeping content packages",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="report whether initialization would change an initialized page",
)
def init(
    dir: str,
    selected: tuple[str, ...],
    no_packages: bool,
    theme: str | None,
    no_theme: bool,
    dry_run: bool,
) -> dict:
    """Create a page directory, recording the packages it selects.

    The author writes PAGE/index.html; every Leaf that serves or checks the page
    composes its layer from the selection. Re-running preserves the page's explicit
    packages unless --package or --no-packages replaces them, and validates the
    current vocabulary and markup. A changed selection restarts its server at the
    same URL; identical initialization leaves it running. --dry-run reports the
    planned change without writing it.
    A package may contain any subset of the package layout, including zero, one,
    or many widgets.
    """
    from leaf.vendoring import cmd_init

    if selected and no_packages:
        raise click.UsageError("--package and --no-packages cannot be used together")
    if theme is not None and no_packages:
        raise click.UsageError("--theme and --no-packages cannot be used together")
    if theme is not None and no_theme:
        raise click.UsageError("--theme and --no-theme cannot be used together")
    if any(not selection for selection in selected):
        raise click.UsageError("--package selections cannot be empty")
    if len(set(selected)) != len(selected):
        raise click.UsageError("each --package selection may appear only once")
    selections = () if no_packages else selected or None
    return cmd_init(
        page_path(dir),
        selections,
        theme=False if no_packages or no_theme else theme,
        dry_run=dry_run,
    )


@cli.group(short_help="Discover personal themes for page authoring.")
def theme() -> None:
    """Discover personal themes for page authoring."""


@theme.command("list", short_help="List personal themes and their author instructions.")
def theme_list() -> dict:
    from leaf.themes import cmd_list

    return cmd_list()


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


@page.command(
    short_help="Check the mutable page source.",
    help=(
        "Check PAGE/index.html.\n\nRuns the markup checks and, where the page has "
        "scripts or widgets only a browser can judge, runs them in the host's "
        "browser. --render also checks the drawn page. The browser is the executable "
        f"{' or '.join(BROWSER_VARIABLES)} names, else the installed Chrome, else "
        "the first browser on PATH; a host with none is told why in place of each "
        "browser check."
    ),
)
@page_argument(renew=False)
@click.option(
    "--render", is_flag=True, help="also check the rendered page in the host's browser"
)
def check(page_dir: Path, render: bool) -> Reported:
    from leaf.validation.command import cmd_check

    report = cmd_check(page_dir, render)
    return Reported(report, report["status"])


@page.command(
    "inspect", short_help="Read page source metrics and browser observations."
)
@page_argument(renew=False)
@click.option(
    "--revision",
    type=click.IntRange(min=1),
    metavar="N",
    help="inspect captured revision N instead of mutable source",
)
@click.option(
    "--compare-to",
    type=click.IntRange(min=1),
    metavar="N",
    help="compare inspected source with captured revision N",
)
def inspect_page(page_dir: Path, revision: int | None, compare_to: int | None) -> dict:
    """Report attributed source inventories and retained browser views as JSON.

    Metrics are observations, not a quality score or a pass/fail check. Opens no
    browser and changes no page state. Browser observations name their own revision,
    viewport and freshness; matches_source says whether they describe these inputs.
    """
    from leaf.page_inspection import cmd_inspect

    return cmd_inspect(page_dir, revision, compare_to)


@page.command()
@page_argument(renew=True)
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    metavar="FILE...",
)
def media(page_dir: Path, files) -> list[dict]:
    """Add images, video, or audio and print their page paths.

    Copies each file into the page under a content-addressed name and prints
    one JSON line per file: its page `path` and its `source` file.
    """
    from leaf.media import cmd_media

    return cmd_media(page_dir, [Path(f) for f in files])


@page.command(short_help="Read selected vocabulary instructions by audience as JSON.")
@page_argument(renew=False)
@click.option(
    "--use",
    "entries",
    multiple=True,
    metavar="ENTRY",
    help="a registry entry you will use, as its key names it; repeat for more",
)
@click.option(
    "--contract",
    "contracts",
    multiple=True,
    metavar="ID",
    help="a data contract you will produce or read; repeat for more",
)
def instructions(
    page_dir: Path, entries: tuple[str, ...], contracts: tuple[str, ...]
) -> dict[str, str]:
    """Print a JSON object mapping each audience, such as `author`, to its instructions.

    Alone, it prints the packages' shared instructions. Before writing markup, name
    each element or idiom you will use with --use, and each data contract with
    --contract; the output then adds their instructions, and those of the entries
    their examples use.
    """
    from leaf.page import page_instructions

    return page_instructions(page_dir, entries=entries, contracts=contracts)


@page.command(short_help="Print the vocabulary the page is written in as JSON.")
@page_argument(renew=False)
def vocabulary(page_dir: Path) -> dict:
    """Print the vocabulary PAGE/index.html is checked against: the layer this Leaf
    composes for the page's packages, with the page's own declarations over it.
    Ordinary keys are element names or CSS selectors; `$` keys are facts shared
    across the layer."""
    from leaf.registry.storage import require_candidate

    return require_candidate(page_dir).registry


@page.command("list", short_help="List this machine's pages and who holds each.")
def page_list() -> list:
    """Print each page on this machine as a JSON line: every serving page, and
    every page a session claimed, served or not.

    A line names the page directory, its title, its `url` (null when nothing
    serves it), and the session that holds it: `claim_session`, the name its
    harness gives it now (`session_name`), the directory it claimed from
    (`session_cwd`), and whether it still runs (`session_alive`). A serving
    page also carries how many rows On me holds (`on_user`) and its open and
    unread thread counts (`threads`). `page state PAGE` reads one page whole."""
    from leaf.presence import page_list as listing

    return listing()


@page.command(short_help="Print where the page, a thread, or a widget stands.")
@page_argument(renew=False)
@click.argument("target", metavar="[MESSAGE_OR_WIDGET]", required=False)
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
def state(
    page_dir: Path, target: str | None, after: int | None, limit: int | None
) -> dict:
    """Print the page as it is now, as one JSON object: the active revision's
    file, the current widget actions and workers' reports, the user's On me list and
    yours, thread summaries, versions, presence, and bound data. Read the active
    revision's HTML beside it for the document.

    MESSAGE_OR_WIDGET narrows the output to what it names. A message, or a widget
    frozen into one, names its thread: the output is that thread with a page of its
    messages, their frozen markup, and the state of its widgets, paged by --after
    and --limit. A widget on the page names itself: its element, its current
    actions and reports, its obligations and to-dos, and its workflows."""
    from leaf.agent_state import cmd_page_state

    return cmd_page_state(page_dir, target, after=after, limit=limit)


@page.command(short_help="Stamp the current source as the next version.")
@page_argument(renew=True)
@body_options("the changelog")
@click.option(
    "--replace",
    type=(click.Path(exists=True, file_okay=False, path_type=Path), str),
    metavar="DIR DIGEST",
    help="replace index.html and page/ together from candidate DIR, if the "
    "source still has DIGEST, the source.digest page state printed",
)
@click.option(
    "--completes",
    multiple=True,
    metavar="WIDGET",
    help="a widget whose open to-dos this version completes (repeatable)",
)
def stamp(
    page_dir: Path,
    text: str | None,
    body_file,
    completes: tuple[str, ...],
    replace: tuple[Path, str] | None,
) -> dict:
    """Stamp PAGE/index.html with a changelog.

    Checks the source first, then records it as the next public version. Repeat
    --completes for each widget whose open to-dos this version completes; it ends
    them done, citing the version. Other to-dos stay open, even when the version
    removes their widget.

    --replace DIR DIGEST replaces index.html and the whole page/ tree from DIR and
    stamps them in one step. DIGEST is source.digest from page state before editing;
    if the source has changed since, the stamp is refused and the page is left as it
    was.
    """
    from leaf.publishing import cmd_stamp

    return cmd_stamp(
        page_dir,
        read_body(text, body_file),
        completes,
        replace=replace,
    )


@page.command(short_help="Export a stamped version to one HTML file.")
@page_argument(renew=False)
@click.option(
    "-o",
    "--out",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="output HTML file",
)
@click.option(
    "--version",
    type=click.IntRange(min=1),
    metavar="N",
    help="stamped version to export (default: latest)",
)
def export(page_dir: Path, out: Path, version: int) -> dict:
    """Export a stamped version to one HTML file that opens offline.

    The file runs the page's own runtime against its captured state, with no Leaf
    server or host behind it.
    """
    from leaf.exporting import cmd_export

    return cmd_export(page_dir, out, version)


@page.command(short_help="Picture a drawing comment as the user saw it.")
@page_argument(renew=False)
@click.argument("message", metavar="MESSAGE")
def picture(page_dir: Path, message: str) -> dict:
    """Draw comment MESSAGE's drawing over the page as the user saw it, and print the
    PNG's path as `file`.

    Opens the comment's revision in the host's browser, with the log applied
    through the comment, at the window size and color scheme the drawing was
    made in, and crops to the ink and the page around it. Bound data is read as
    it stands now, and the host's fonts may differ from the user's.
    """
    from leaf.render_gate.picture import cmd_picture

    return cmd_picture(page_dir, message)


@page.command(
    short_help="Report a state change onto a page widget, as a worker.",
)
@page_argument(renew=True)
@click.argument("widget", metavar="WIDGET")
@click.argument("verb", metavar="VERB")
@click.argument("fields", metavar="[NAME=VALUE]...", nargs=-1)
def report(page_dir: Path, widget: str, verb: str, fields: tuple) -> dict:
    """Report a state change onto a page widget, as a worker.

    VERB is one of the widget's agent-written x-state verbs, and each NAME=VALUE one of
    its fields: `leaf page report <page> t-parser status value=review text="Ready for
    review"` moves a task. The page shows the report at once, marked provisional,
    until a stamped version writes it into the markup or overrules it.
    """
    from leaf.reports import cmd_report

    return cmd_report(page_dir, widget, verb, fields)


@page.command(short_help="Print the event log as JSON lines.")
@page_argument(renew=False)
@click.option(
    "--after",
    type=click.IntRange(min=0),
    default=0,
    metavar="SEQ",
    help="print events after this sequence",
)
@click.option(
    "--follow",
    is_flag=True,
    help="keep printing each event as it is appended, until stopped",
)
def events(page_dir: Path, after: int, follow: bool) -> None:
    """Print the event log as JSON lines.

    Each line is one stored event record; `seq` is its position, and `--after`
    resumes from the last one a reader saw. This is read-only and does not
    acknowledge user events. `page state PAGE MESSAGE_OR_WIDGET` reads one thread or
    widget.
    """
    from leaf.event_log import cmd_events

    cmd_events(page_dir, after, follow=follow)


@page.command(short_help="Read browser interactions and request diagnostics.")
@page_argument(renew=False)
@click.option(
    "--session", help="one browser tab's records, without unassociated server requests"
)
@click.option(
    "--since",
    metavar="ISO_TIME",
    help="include observations at or after this time, with its timezone offset",
)
@click.option(
    "--until",
    metavar="ISO_TIME",
    help="exclude observations at or after this time, with its timezone offset",
)
@click.option(
    "--type",
    "types",
    multiple=True,
    help="an observation type to include; repeat for more",
)
def interactions(
    page_dir: Path,
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
        page_dir,
        session=session,
        since=start,
        until=stop,
        types=types,
    )


@page.command(short_help="Connect a page to this session.")
@page_argument(renew=True)
@click.option(
    "--manual-delivery",
    is_flag=True,
    help="claim for an explicit leaf wait watcher instead of preparing harness delivery",
)
def claim(page_dir: Path, manual_delivery: bool) -> dict:
    """Connect PAGE's updates to this session without changing its server.

    Delivery is ready before ownership moves. A watch another session runs on PAGE
    stops watching it. --manual-delivery leaves delivery to your explicit leaf wait.
    """
    from leaf.service import cmd_claim

    return cmd_claim(page_dir, manual_delivery=manual_delivery)


@cli.group(short_help="Read a delivery by its id, and confirm you received it.")
def delivery() -> None:
    """Read a delivery that Leaf names by its id instead of printing it, as a
    `<leaf-delivery>` pointer, and confirm you received it.

    Run `leaf delivery read <id>`, and each part's `next` command until none is
    left, then follow the `acknowledge` instruction the last part carries.
    Confirming a delivery marks its updates Delivered for the user."""


@delivery.command("read", short_help="Print a delivery, one part at a time.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
@click.option(
    "--part",
    type=click.IntRange(min=1),
    default=1,
    help="this numbered part of a large delivery",
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
    read Delivered."""
    from leaf.delivery import cmd_delivery_ack

    cmd_delivery_ack(delivery_id)


@cli.group(short_help="Create, answer, edit, summarize, or resolve a thread.")
def thread() -> None:
    """Create and answer threads as the agent, and maintain them.

    Every write prints the records it appended, one JSON line each, as `page
    events` prints them. `page state PAGE MESSAGE` reads one thread."""


@thread.command("summarize", short_help="Summarize a contiguous message range.")
@page_argument(renew=True)
@click.option(
    "--from",
    "from_message",
    required=True,
    metavar="MESSAGE",
    help="the first message folded",
)
@click.option(
    "--through",
    "through_message",
    required=True,
    metavar="MESSAGE",
    help="the last message folded",
)
@body_options("the summary's Markdown")
@click.option("--label", help="disclosure label (default: Earlier discussion)")
def thread_summarize(
    page_dir: Path,
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
        page_dir,
        from_message,
        through_message,
        read_body(text, body_file),
        label=label,
    )


@cli.group(short_help="Manage a page's access to local files.")
def file() -> None:
    """Grant or withdraw access to explicitly chosen local text files."""


@file.command("bind", short_help="Grant a page read/write access to one file.")
@page_argument(renew=True)
@click.argument("binding", metavar="ID")
@click.argument("path", type=click.Path(path_type=Path), metavar="PATH")
def file_bind(page_dir: Path, binding: str, path: Path) -> dict:
    """Use ID in <lf-file-editor binding=\"ID\"> to edit PATH. Prints the binding,
    the file it grants, and its size in bytes."""
    from leaf.file_bindings import bind_file

    return bind_file(page_dir, binding, path)


@file.command("unbind", short_help="Withdraw a page's access to one bound file.")
@page_argument(renew=True)
@click.argument("binding", metavar="ID")
def file_unbind(page_dir: Path, binding: str) -> dict:
    """Remove ID's grant. The file and its saved edits stay intact; later reads
    find no file and saves are refused, including from already-open editors."""
    from leaf.file_bindings import unbind_file

    return unbind_file(page_dir, binding)


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


@cli.group(short_help="Grant pages authenticated HTTPS reads.")
def connection() -> None:
    """Host credentials and origin grants for page-authored integrations."""


@connection.command(
    "bind", short_help="Grant authenticated GET access to an HTTPS origin."
)
@page_argument(renew=True)
@click.argument("name")
@click.argument("origin")
@click.option(
    "--credential-env",
    required=True,
    help="the environment variable holding the credential, read as you bind",
)
@click.option(
    "--header",
    default="Authorization",
    show_default=True,
    help="the request header that carries the credential",
)
@click.option(
    "--prefix",
    default="Bearer ",
    show_default=True,
    help="text sent before the credential in that header",
)
@click.option(
    "--max-requests",
    default=200,
    type=click.IntRange(min=1),
    show_default=True,
    help="requests the page may make before it must be bound again",
)
def connection_bind(
    page_dir: Path,
    name: str,
    origin: str,
    credential_env: str,
    header: str,
    prefix: str,
    max_requests: int,
) -> dict:
    """Bind NAME to ORIGIN. Rebinding renews its request allowance.

    The credential is read from the binding process's environment and stored
    privately on this host, outside page files and exports.
    """
    from leaf.http_connections import bind

    return bind(
        page_dir,
        name,
        origin,
        credential_env=credential_env,
        header=header,
        prefix=prefix,
        max_requests=max_requests,
    )


@connection.command("unbind", short_help="Withdraw one page connection.")
@page_argument(renew=True)
@click.argument("name")
def connection_unbind(page_dir: Path, name: str) -> dict:
    """Withdraw NAME's grant for later requests; one already sent may finish."""
    from leaf.http_connections import unbind

    return unbind(page_dir, name)


@cli.group(short_help="Set or clear page-bound external data.")
def data() -> None:
    """Manage each bound source's current value, one JSON file per source."""


@data.command("set", short_help="Replace one bound source value.")
@page_argument(renew=True)
@click.argument("source", metavar="SOURCE")
@body_options("the JSON value")
def data_set(page_dir: Path, source: str, text: str | None, body_file) -> dict:
    """Validate and replace SOURCE with one complete JSON value."""
    from leaf.data import cmd_data_set

    value = json_body(text, body_file)
    return cmd_data_set(page_dir, source, value)


@data.command("clear", short_help="Remove one source's current value.")
@page_argument(renew=True)
@click.argument("source", metavar="SOURCE")
def data_clear(page_dir: Path, source: str) -> dict:
    """Remove SOURCE's current value; its next write uses the current binding."""
    from leaf.data import cmd_data_clear

    return cmd_data_clear(page_dir, source)


@cli.group(short_help="Start, run, or stop the local server.")
def server() -> None:
    """Start, run, or stop the local server."""


LIFETIMES = {
    "session": "claimed by this agent session, ending when no live session claims "
    "the page (persistent from a shell outside any session)",
    "persistent": "declines the session claim, so only `leaf server stop` ends it, "
    "for a page kept up across sessions",
    "temporary": "serves on loopback for this command only, without claiming the page",
}


def serve_flags(*lifetimes: str):
    """The statements a serve takes: `--lifetime`, among `lifetimes`, and `--host`.
    `server start` hands both to the `server _serve` it spawns
    (`hosting._starting_server`), so one spelling keeps the pair from drifting. The values are the `lifetime` a started
    server prints (`hosting.server_reading`)."""

    def decorate(command):
        command = click.option(
            "--host",
            metavar="NAME",
            help="bind every interface and put NAME in the URL, for a user the "
            "derived address can't reach; recorded in service.json",
        )(command)
        return click.option(
            "--lifetime",
            type=click.Choice(lifetimes),
            default="session",
            show_default=True,
            help="; ".join(f"{name}: {LIFETIMES[name]}" for name in lifetimes),
        )(command)

    return decorate


@server.command(short_help="Start a page's server and print its URL.")
@page_argument(renew=True)
@serve_flags("session", "persistent")
def start(page_dir: Path, host: str | None, lifetime: str) -> dict:
    """Start a page's server and print its URL.

    Returns once the server and this harness's watcher are ready; the server
    itself keeps running in a session of its own. `leaf server stop` takes one
    down, and a session server goes down with the session that claimed it
    besides. A page already served reconnects delivery and prints that server's
    URL. A persistent server claims no page and prepares no agent delivery. Beside
    the URL it prints the server's lifetime, the page's layer and the Leaf serving
    it.
    """
    from leaf.hosting import claim_and_start, started_server

    with claim_and_start(page_dir, host, lifetime == "persistent") as started:
        pass
    return started_server(page_dir, started.url)


@server.command(short_help="Serve a page in the foreground until stopped.")
@page_argument(renew=True)
@serve_flags("session", "persistent", "temporary")
def run(page_dir: Path, host: str | None, lifetime: str) -> None:
    """Serve a page in the foreground, printing its URL and running until stopped.

    Run this in a terminal of your own to hold a page up where you can watch it.
    Browser harnesses use `--lifetime temporary`; a user page in an agent session
    uses `server start`. A page already served prints that server's URL and exits.
    """
    from leaf.harness import session_harness
    from leaf.hosting import cmd_serve, cmd_serve_temporary
    from leaf.leases import release_on_termination

    # As for `_serve`, except that a temporary server, which holds no lease,
    # unwinds on every stop.
    release_on_termination()
    if lifetime == "temporary":
        cmd_serve_temporary(page_dir, host)
        return
    cmd_serve(
        page_dir,
        host,
        lifetime == "persistent",
        harness=session_harness(),
        acquire=True,
    )


@server.command("_serve", hidden=True)
# Renewing the layer here would restart the server this process is becoming.
@page_argument(renew=False)
@serve_flags("session", "persistent")
@click.option("--revive", is_flag=True, hidden=True)
@click.option("--acquire", is_flag=True, hidden=True)
@click.option("--claim", hidden=True)
@click.option("--harness", required=True, hidden=True)
@click.option("--handshake", type=int, required=True, hidden=True)
def _serve(
    page_dir: Path,
    host: str | None,
    lifetime: str,
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

    # Until the server commits its service, a SIGTERM or SIGHUP unwinds and
    # retires what preparation holds. From then on a stop signal ends the process
    # through `exit_serving` (`server.exit_serving_on_signals`).
    release_on_termination()
    with Handshake(handshake) as answer:
        cmd_serve(
            page_dir,
            host,
            lifetime == "persistent",
            revive,
            harness=harness_from_argument(harness),
            handshake=answer,
            acquire=acquire,
            prepared_claim=json.loads(claim) if claim is not None else None,
        )


@server.command(short_help="Stop a page's server.")
@page_argument(renew=False)
def stop(page_dir: Path) -> dict:
    """Stop a page's server."""
    from leaf.hosting import cmd_stop

    return {"stopped": cmd_stop(page_dir)}


@page.command("open", short_help="Keep a page available for feedback.")
@page_argument(renew=True)
def page_open(page_dir: Path) -> dict:
    """Keep PAGE available for feedback and put down current work.

    This clears every task start; to-dos and unanswered updates stay owed.
    To request an answer, send a thread message with --obligation so the
    question appears in On me. Opening a page creates no obligation.
    """
    from leaf.session import cmd_waiting

    return cmd_waiting(page_dir)


@page.command("close", short_help="Finish a page and stop watching for feedback.")
@page_argument(renew=True)
def page_close(page_dir: Path) -> dict:
    """Finish PAGE and stop watching for feedback.

    Refuses while updates, workers' reports or page errors remain unread,
    updates need an answer, or agent to-dos remain open. Closing puts down
    every task start and settles no obligation.
    """
    from leaf.session import cmd_idle

    return cmd_idle(page_dir)


@cli.command(
    short_help="Wait for the next batch.",
    help=(
        "Watch every page this session holds, or observe PAGE without taking "
        "ownership. Claim a foreign page explicitly with `leaf page claim`.\n\n"
        + WAIT_BATCH_OUTPUT_INSTRUCTION
    ),
)
@page_argument(renew=False, required=False)
def wait(page_dir: Path | None) -> int:
    """Wait for the next batch."""
    from leaf.leases import release_on_termination
    from leaf.session import cmd_wait

    release_on_termination()
    return cmd_wait(page_dir)


def _obligation_option(command):
    return click.option(
        "--obligation",
        is_flag=True,
        help="put this message on On me until the user replies or settles it",
    )(command)


def _title_option(command):
    return click.option(
        "--title",
        help=(
            "name the thread for the panel unless it has a name: a few words, at "
            "most 80 characters"
        ),
    )(command)


@thread.command(
    "create", short_help="Create an agent thread — on a passage, or on the page whole."
)
@page_argument(renew=True)
@click.option("--quote", help="passage text from the active revision")
@click.option("--section", metavar="ID", help="element ID to anchor or scope --quote")
@click.option("--part", metavar="ID", help="declared visual part within --section")
@body_options("the comment's text")
@click.option("--markup", help="HTML fragment after the text, validated here")
@_title_option
@_obligation_option
def thread_create(
    page_dir: Path,
    quote: str,
    section: str,
    part: str,
    text: str | None,
    body_file,
    markup: str,
    title: str | None,
    obligation: bool,
) -> dict:
    """Create a thread as the agent: anchored where --quote or
    --section points at a passage, general where neither does — a question about
    the work as a whole.

    Use --obligation when the next move is the user's: the message waits on
    On me until their reply or settling reaction. Refuses a quote the active revision does not
    hold, or holds more than once. The comment's id is the thread's.
    """
    from leaf.thread import cmd_comment

    return cmd_comment(
        page_dir,
        quote,
        section,
        part,
        read_body(text, body_file),
        markup,
        title=title,
        obligation=obligation,
    )


@thread.command(
    "reply", short_help="Reply using an answer reference or a page and message."
)
@click.argument("destination", metavar="REFERENCE_OR_PAGE")
@click.argument("message", metavar="[MESSAGE]", required=False)
@click.option(
    "--done", is_flag=True, help="the reply delivers what the message asked for"
)
@body_options("the reply's text")
@click.option("--markup", default="", help="frozen HTML fragment after the text")
@click.option(
    "--todo",
    metavar="TITLE",
    help="the reply promises work it doesn't deliver; opens that to-do on the "
    "thread, ended by `leaf task end` with the reply's id",
)
@click.option("--ephemeral", is_flag=True, help="one-line progress, without answering")
@_title_option
@_obligation_option
@click.option("--quote", help="new passage text to move this thread onto")
@click.option("--section", metavar="ID", help="new element ID, or scope for --quote")
@click.option("--part", metavar="ID", help="new declared visual part within --section")
@click.option("--detach", is_flag=True, help="remove the thread's page target")
def thread_reply(
    destination: str,
    message: str | None,
    done: bool,
    **options,
) -> dict | None:
    """Answer a delivered update by its `answer.ref` alone, or post into the
    thread PAGE MESSAGE names, which is refused while that thread owes an answer.

    An answer declares what it leaves with --done, --todo or --obligation, or
    carries a widget in --markup that asks; --ephemeral progress declares nothing,
    and --done needs a reference. The reply
    publishes your saved page edits, checked as `page check` checks them without a
    browser. The Leaf skill's references/threads.md says which to use and what
    each leaves.
    """
    from leaf.thread import post_reply, post_response

    text = read_body(options.pop("text"), options.pop("body_file"))
    if message is not None:
        if done:
            raise click.UsageError(
                "use an answer reference with --done; "
                "use `leaf thread reply <answer.ref>`"
            )
        return post_reply(
            resolve_dir(destination),
            {"parent": message},
            text,
            validate_source=True,
            **options,
        )

    declared = [
        flag
        for flag, given in (
            ("--done", done),
            ("--todo", options["todo"] is not None),
            ("--obligation", options["obligation"]),
        )
        if given
    ]
    if len(declared) > 1:
        raise click.UsageError(f"{' and '.join(declared)} cannot be used together")
    answers = not options["ephemeral"]
    if declared and not answers:
        raise click.UsageError(
            f"{declared[0]} declares what an answer leaves; progress answers nothing"
        )
    # An answer that declares nothing must carry a widget that asks; `post_reply`
    # refuses it otherwise (`undeclared-answer`).
    options["asks_back"] = not declared and answers
    return post_response(destination, text, **options)


@thread.command("edit", short_help="Edit a message's text, or its thread's title.")
@page_argument(renew=True)
@click.argument("message", metavar="MESSAGE")
@body_options("the replacement text")
@click.option(
    "--title",
    help="rename MESSAGE's thread for the panel: a few words, at most 80 characters",
)
def thread_edit(
    page_dir: Path, message: str, text: str | None, body_file, title: str | None
) -> list[dict]:
    """Replace the visible text of MESSAGE, an agent-authored comment or reply,
    or with --title rename the thread MESSAGE is in, whoever opened it. --title
    alone leaves the text as it is.

    Frozen markup is not editable. Keep a title stable unless the thread's subject
    changes.
    """
    from leaf.thread import cmd_edit

    renames_only = title is not None and text is None and body_file is None
    body = None if renames_only else read_body(text, body_file)
    return cmd_edit(page_dir, message, body, title=title)


@thread.command("resolve", short_help="Close a thread as the agent.")
@page_argument(renew=True)
@click.argument("message", metavar="MESSAGE")
def thread_resolve(page_dir: Path, message: str) -> dict:
    """Close the thread MESSAGE is in, as the agent.

    The user ordinarily closes a thread; the Leaf skill's
    references/threads.md says when the agent does.
    """
    from leaf.thread import cmd_resolve

    return cmd_resolve(page_dir, message)


@cli.group(short_help="Create or end to-dos, start work on your list, and plan.")
def task() -> None:
    """Create and end to-dos, say which item on your list you are working on, and
    lay out your plan.

    Your list, On <your name>, holds each update you owe an answer and each to-do
    you opened; a to-do `--on user` is on the user's On me instead. Every write
    prints the record it appended, one JSON line, as `page events` prints it. The
    Leaf skill's references/conversation-loop.md, "Long-running work" and "The On
    lists", says when to use each.
    """


@task.command("create", short_help="Create a to-do, yours or the user's.")
@page_argument(renew=True)
@click.argument("subject", metavar="SUBJECT")
@click.option("--title", required=True, help="the to-do, in a few words")
@click.option(
    "--on",
    "owner",
    type=click.Choice(["agent", "user"]),
    default="agent",
    show_default=True,
    help="whose list the to-do is on: yours, or the user's On me",
)
def task_create(page_dir: Path, subject: str, title: str, owner: str) -> dict:
    """Create a to-do titled --title on SUBJECT and print it; its `id` names it later.

    SUBJECT is a thread id, an element's id, or `page` for the whole page.
    Your own to-do on a widget needs a widget that declares x-work or holds an
    unsettled update. With `--on user` the to-do is the user's: their Done ends it,
    and you can end it too. A thread attachment provides discussion context;
    replying does not complete the task. For a conversational request instead,
    send the message with --obligation."""
    from leaf.todos import cmd_create

    return cmd_create(page_dir, subject, title, owner)


@task.command(
    "start", short_help="Start work on an update or to-do, with its status line."
)
@page_argument(renew=True)
@click.argument("item", metavar="ID")
@click.option(
    "--text", "line", required=True, help="what you are doing, in one sentence"
)
def task_start(page_dir: Path, item: str, line: str) -> dict:
    """Mark ID Working for this turn, with --text saying what you are doing.

    ID is the event id of a user update you owe, as its delivery names it, or an
    open to-do's id. --text names the work and its subject in one sentence; it shows
    beside the update or to-do and in Leaf's panel. Your answer to the update, or the
    to-do's end, ends the start. If your turn ends first, the update or to-do reads stalled
    until you answer it or start it again."""
    from leaf.todos import cmd_start

    return cmd_start(page_dir, item, line)


@task.command("end", short_help="End a to-do or settle a conversational obligation.")
@page_argument(renew=True)
@click.argument("task_id", metavar="ID")
@click.argument("outcome", type=click.Choice(["done", "failed", "dropped"]))
@click.option("--text", "detail", help="where the result is, or why there is none")
def task_end(page_dir: Path, task_id: str, outcome: str, detail: str | None) -> dict:
    """End the to-do or conversational obligation named by ID in `page state`.

    A to-do, yours or the user's, ends done, failed or dropped. --text says where
    the result is, such as the version or reply holding it, or why there is none.

    For a message obligation (`message:<id>`) or a question widget answered in
    words (`widget:<id>`), done records that the user answered elsewhere, --text
    saying where; dropped withdraws the question. These outcomes record no answer
    from the user. A widget answered through its controls ends through its state
    or an authored withdrawal.
    """
    from leaf.todos import cmd_end

    return cmd_end(page_dir, task_id, outcome, detail)


@task.command("plan", short_help="Write your plan for the page's work as one outline.")
@page_argument(renew=True)
@body_options("the JSON outline")
def task_plan(page_dir: Path, text: str | None, body_file) -> dict:
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
    return cmd_plan(page_dir, steps)
