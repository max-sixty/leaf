"""Count what the pages kept on this machine used: widgets, packages, commands and `leaf` commands.

    leaf-dev usage [--since ISO] [--json]

Regular maintenance asks who would notice a mechanism gone (`/developing-leaf`,
"Regular maintenance"). This answers from the record rather than from the tree: a
widget an example shows and no page ever held, a key nobody pressed in a month, a
`leaf` command no agent ran. It reads every page directory under the state home's
`pages/`, so it counts the people and agents who worked on this machine, and a
feature they never needed here may still matter elsewhere. Read a zero as a question
to put to the maintainer, with what the feature costs beside it.

- **Widgets**: each tag a bundled registry declares, with the pages whose current
  source holds it. A page that used a widget and later dropped it doesn't count.
- **Packages**: the packages each page's layer record selects, for the pages whose
  record this Leaf reads. A record at another shape, an older Leaf's or a newer
  one's, counts as none, where `page init` would refuse the newer one.
- **Commands**: each command a person ran, by key or by press, from the `command`
  observations a tab writes (`browser/runtime/interaction-log.js`), with the sessions
  and pages it ran in. A session whose browser calls itself headless is a check or a
  probe driving the page, not a person, and is left out. Only commands that ran are
  listed: the runtime registers them as each page's widgets load, so no file lists
  them all. A widget that registers a command per element, as `lf-options` does per
  option, shows as one row ending `-*`.
- **`leaf` commands**: each command the CLI declares, with the runs agents made
  against a page (`leaf.interaction_log.record_command`). A command that names no
  page, such as `leaf wait` over a session's pages, records nothing.

`--since` bounds the observations and `leaf` commands by host time; widgets and
packages describe each page as it stands.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import click

from leaf.interaction_log import read_interactions
from leaf.registry.storage import LAYER
from leaf.schema import LAYER_FILE
from leaf.state import state_home
from leaf_dev import ROOT


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.seen: Counter[str] = Counter()

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self.seen[tag] += 1


def declared_widgets() -> dict[str, str]:
    """Each element a bundled registry declares, with the package that declares it.
    A registry also keys layer facts under `$` and idioms under a selector."""
    registries = [ROOT / "browser" / "registry.json"]
    registries += sorted((ROOT / "packages").glob("*/registry.json"))
    return {
        key: "kernel" if path.parent.name == "browser" else path.parent.name
        for path in registries
        for key in json.loads(path.read_text())
        if re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)+", key)
    }


def declared_leaf_commands() -> list[str]:
    """Every command `leaf` shows in its help, as an agent types it."""
    from leaf.cli import cli

    def walk(group: click.Group, prefix: str) -> list[str]:
        names = []
        for name, command in group.commands.items():
            if command.hidden:
                continue
            if isinstance(command, click.Group):
                names += walk(command, f"{prefix}{name} ")
            else:
                names.append(f"{prefix}{name}")
        return names

    return sorted(walk(cli, ""))


def families(ids: list[str]) -> dict[str, str]:
    """Each command id's row: its own, or `stem-*` where ten or more ids share the stem
    before the first hyphen of their last part, as ids minted per element do."""
    stems = {
        command: command[: command.index("-", command.rindex(".") + 1)]
        for command in ids
        if "." in command and "-" in command[command.rindex(".") :]
    }
    crowded = {stem for stem, n in Counter(stems.values()).items() if n >= 10}
    return {
        command: f"{stems[command]}-*" if stems.get(command) in crowded else command
        for command in ids
    }


def survey(pages: list[Path], since: datetime | None) -> dict:
    widgets = declared_widgets()
    held: dict[str, set[str]] = defaultdict(set)
    uses: Counter[str] = Counter()
    selected: Counter[str] = Counter()
    layered = 0
    ran: dict[str, Counter[str]] = defaultdict(Counter)
    ran_on: dict[str, set[str]] = defaultdict(set)
    cli_runs: Counter[str] = Counter()
    cli_pages: dict[str, set[str]] = defaultdict(set)
    people = set()
    for page in pages:
        source = page / "index.html"
        if source.exists():
            tags = _Tags()
            tags.feed(source.read_text(errors="replace"))
            for tag, count in tags.seen.items():
                if tag in widgets:
                    held[tag].add(page.name)
                    uses[tag] += count
        if record := LAYER.read(page / LAYER_FILE):
            layered += 1
            for package in record["packages"]:
                selected[Path(package).name] += 1
        rows = read_interactions(
            page, since=since, types=("session_start", "command", "leaf_command")
        )
        headless = {
            row["session"]
            for row in rows
            if row["type"] == "session_start" and "Headless" in row.get("userAgent", "")
        }
        for row in rows:
            if row["type"] == "leaf_command":
                cli_runs[row["command"]] += 1
                cli_pages[row["command"]].add(page.name)
            elif row["type"] == "command" and row["session"] not in headless:
                ran[row["id"]][row["session"]] += 1
                ran_on[row["id"]].add(page.name)
                people.add(row["session"])
    family = families(list(ran))
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    grouped_on: dict[str, set[str]] = defaultdict(set)
    for command, sessions in ran.items():
        grouped[family[command]] += sessions
        grouped_on[family[command]] |= ran_on[command]
    ran, ran_on = grouped, grouped_on
    return {
        "pages": len(pages),
        "pages_with_layer_record": layered,
        "sessions": len(people),
        "widgets": [
            {
                "tag": tag,
                "package": package,
                "pages": len(held[tag]),
                "uses": uses[tag],
            }
            for tag, package in widgets.items()
        ],
        "packages": dict(selected),
        "commands": [
            {
                "id": command,
                "runs": sum(sessions.values()),
                "sessions": len(sessions),
                "pages": len(ran_on[command]),
            }
            for command, sessions in ran.items()
        ],
        "leaf_commands": [
            {
                "command": command,
                "runs": cli_runs[command],
                "pages": len(cli_pages[command]),
            }
            for command in sorted(set(declared_leaf_commands()) | set(cli_runs))
        ],
    }


def _table(rows: list[tuple]) -> None:
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        click.echo(
            "  ".join(
                str(cell).rjust(width)
                if isinstance(cell, int)
                else str(cell).ljust(width)
                for cell, width in zip(row, widths, strict=True)
            ).rstrip()
        )


@click.command()
@click.option(
    "--since", help="Count observations and `leaf` commands from this ISO time."
)
@click.option("--json", "as_json", is_flag=True, help="Print the survey as JSON.")
def usage(since: str | None, as_json: bool) -> None:
    """Count what this machine's pages used: widgets, packages, commands, `leaf` commands."""
    pages = sorted(page for page in (state_home() / "pages").iterdir() if page.is_dir())
    result = survey(pages, datetime.fromisoformat(since) if since else None)
    if as_json:
        click.echo(json.dumps(result, indent=2))
        return
    click.echo(
        f"{result['pages']} pages, {result['sessions']} sessions that ran a command\n"
    )
    click.echo("Widgets, by pages whose source holds them")
    _table(
        [("pages", "uses", "tag", "package")]
        + [
            (row["pages"], row["uses"], row["tag"], row["package"])
            for row in sorted(result["widgets"], key=lambda row: -row["pages"])
        ]
    )
    click.echo(
        f"\nPackages selected, of {result['pages_with_layer_record']} pages with a layer record"
    )
    _table(
        [("pages", "package")]
        + [(count, name) for name, count in Counter(result["packages"]).most_common()]
    )
    click.echo("\nCommands people ran")
    _table(
        [("runs", "sessions", "pages", "id")]
        + [
            (row["runs"], row["sessions"], row["pages"], row["id"])
            for row in sorted(result["commands"], key=lambda row: -row["runs"])
        ]
    )
    click.echo("\n`leaf` commands agents ran against a page")
    _table(
        [("runs", "pages", "command")]
        + [
            (row["runs"], row["pages"], row["command"])
            for row in sorted(result["leaf_commands"], key=lambda row: -row["runs"])
        ]
    )
