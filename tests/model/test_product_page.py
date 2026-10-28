"""The product pages are Leaf documents using the site's composed vocabulary."""

import json
import re
import shlex
from pathlib import Path

import click
from click.testing import CliRunner
from leaf_dev.page_fixtures import authored_markup
from unidiff import PatchSet

from leaf import cli as cli_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf.registry import validation as registry_validation
from leaf.registry.schema import check_schema
from leaf.registry.storage import load_registry
from leaf.state import kernel_registry
from leaf.structure import SourceDocument
from leaf.validation import composition as validation_model

ROOT = Path(__file__).parents[2]
ASSETS = ROOT / "browser"
DEFAULT_PACKAGE = ROOT / "packages" / "default"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
DEVELOPER_PAGES = tuple(sorted((EXAMPLES / "developer").glob("*.html")))


def test_kernel_event_contracts_declare_closed_records():
    events = kernel_registry()["$events"]["kinds"]
    assert events
    envelope = {"id", "ts", "author", "kind", "seq"}
    for kind, contract in events.items():
        # A contract's other members classify the kind (`$events.description`).
        for member in ("record", "browser"):
            if member in contract:
                check_schema(contract[member])
        record = contract["record"]
        properties = record["properties"]
        assert record["type"] == "object"
        assert record["additionalProperties"] is False
        assert properties["kind"] == {"const": kind}
        assert envelope <= set(properties)
        assert envelope <= set(record["required"])


def test_docs_pages_leave_delivery_markup_to_leaf():
    pages = sorted(DOCS.glob("*.html"))
    assert pages
    for page in pages:
        text = page.read_text()
        assert 'href="/theme.css"' not in text, page.name
        assert 'src="/leaf.js"' not in text, page.name
        assert "Content-Security-Policy" not in text, page.name
        assert '<body class="site-page' in text, page.name


def test_every_published_source_says_what_its_page_is():
    """A search result and an unfurled link show the title and the description.

    The build composes the rest of a page's card from these two and refuses a page
    without them, so the failure this catches is one that would stop a deploy.
    """
    sources = [
        *DOCS.glob("*.html"),
        *(page for page in EXAMPLES.glob("*.html") if page.stem != "corpus"),
        *DEVELOPER_PAGES,
    ]
    descriptions = {}
    for page in sorted(sources):
        parsed = SourceDocument(page.read_text())
        described = [
            meta["content"]
            for meta in parsed.authoring.named_metas
            if meta["name"] == "description"
        ]
        assert parsed.authoring.title.strip(), page.name
        assert len(described) == 1, page.name
        assert described[0].strip(), page.name
        descriptions[page.name] = described[0]
    # A description repeated across pages tells a user nothing about which one
    # they found, and search engines fold the duplicates together.
    assert len(set(descriptions.values())) == len(descriptions)


def links(name: str) -> set[tuple[str, str]]:
    """Each link one product source authors, as its target and its text."""
    tree = SourceDocument((DOCS / name).read_text()).tree
    return {(link.attrs["href"], link.text) for link in tree.select("a[href]")}


def test_extension_references_follow_the_concepts_they_explain():
    extending = {href for href, _ in links("extending.html")}
    assert {"/registry/", "/event-log/"} <= extending
    assert {("/registry/", "registry"), ("/event-log/", "event log")} <= links(
        "how-it-works.html"
    )
    assert "/extending/" in {href for href, _ in links("registry.html")}


def test_package_catalog_routes_every_optional_package_to_inspectable_content():
    tree = SourceDocument((DOCS / "extending.html").read_text()).tree
    cards = tree.select("a.package-card")
    declared = json.loads((EXAMPLES / "layer.json").read_text())

    assert [card.attrs["data-package"] for card in cards] == declared
    for card in cards:
        href = card.attrs["href"]
        if href.startswith("/examples/"):
            assert href.endswith("/")
        else:
            source_prefix = "https://github.com/max-sixty/leaf/blob/main/"
            assert href.startswith(source_prefix)
            assert (ROOT / href.removeprefix(source_prefix)).is_file()


def test_package_tutorial_registry_entry_is_valid(page_dir):
    tree = SourceDocument((DOCS / "extending.html").read_text()).tree
    entry = json.loads(tree.select_one("#callout-registry").text)
    registry = load_registry(page_dir) | entry

    registry_validation.validate_registry(registry, "package tutorial")
    validation_model.validate_registry_examples(registry, "package tutorial")


EVENT_LOG = DOCS / "event-log.html"


def code_block(page: SourceDocument, block_id: str) -> str:
    """The text of one authored `lf-code`'s `<pre>`."""
    return page.tree.select_one(f"lf-code#{block_id} > pre").text


def test_pr_walkthrough_excerpts_match_the_captured_patch():
    """Review evidence quotes the captured revision at its shown coordinates.

    Source excerpts and the inline orchestration hunk must agree with the same
    capture the complete patch widget presents, including their source locations.
    """
    source = (EXAMPLES / "pr-walkthrough.html").read_text()
    page = SourceDocument(source)
    manifest = json.loads((EXAMPLES / "pr-walkthrough.data.json").read_text())
    patch_source = page.tree.select_one("#pr-exact-patch").attrs["source"]
    capture = manifest["$captures"][patch_source]
    patch = PatchSet((EXAMPLES / capture["file"]).read_text())
    files = {file.path: file for file in patch}
    blocks = page.tree.select("lf-code")
    assert blocks
    for block in blocks:
        block_id = block.attrs["id"]
        label = page.tree.select_one(f"#{block_id}-source")
        path = label.select_one("code").text
        right = {
            line.target_line_no: line.value
            for hunk in files[path]
            for line in hunk
            if line.target_line_no is not None
        }
        numbers = []
        for interval in block.attrs["lines"].split(","):
            bounds = [int(bound) for bound in interval.split("-")]
            numbers.extend(range(bounds[0], bounds[-1] + 1))
        assert numbers == sorted(set(numbers)), block_id
        assert block.select_one("pre").text.lstrip("\n") == "".join(
            right[n] for n in numbers
        ), block_id

    inline = page.tree.select_one("#pr-key-hunk pre").text.lstrip("\n")
    [shown] = PatchSet(inline)
    captured = files[shown.path]
    assert shown
    assert (shown.source_file, shown.target_file) == (
        captured.source_file,
        captured.target_file,
    )
    assert shown.patch_info == captured.patch_info
    for hunk in shown:
        assert str(hunk) in [str(candidate) for candidate in captured], shown.path


def shown_log(records: list[dict]) -> str:
    """Stored records as the event-log page prints them: each record's JSON as
    `leaf page events` writes it, broken before and after each object-valued field and
    before `id`, so a record reads in a few lines rather than one wide one. An
    object too long for one line puts each of its members on a line of its own,
    including nested state definitions and their detail schemas."""
    width = 96

    def field(key, value, indent=0):
        line = f"{json.dumps(key)}: {json.dumps(value)}"
        if not isinstance(value, dict) or len(line) + indent <= width:
            return line
        members = [field(k, v, indent + 2) for k, v in value.items()]
        return (
            f"{json.dumps(key)}: {{" + (",\n" + " " * (indent + 3)).join(members) + "}"
        )

    shown = []
    for record in records:
        groups, current = [], []
        for key, value in record.items():
            nested = isinstance(value, dict)
            if current and (nested or key == "id"):
                groups.append(current)
                current = []
            current.append(field(key, value))
            if nested:
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        shown.append("{" + ",\n ".join(", ".join(group) for group in groups) + "}")
    return "\n".join(shown)


def test_the_event_log_page_shows_the_records_the_door_writes(page_dir):
    """The page's log was captured from its own sample driven in a browser. The
    commands it records go back through the append door on the same markup, and
    what the door stores now has to be what the page shows, `id` and `ts` aside.
    A changed field, meaning, or refusal fails here with the records to paste."""
    source = SourceDocument(EVENT_LOG.read_text())
    sample = source.tree.select_one("lf-sample#try-sample").inner_html
    (page_dir / "index.html").write_text(
        '<!doctype html><html lang="en"><head><title>Release question</title>'
        '<meta name="description" content="The sample."></head>'
        f"<body><main>{sample}</main></body></html>"
    )
    stamped = CliRunner().invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "v1"]
    )
    assert stamped.exit_code == 0, stamped.output

    shown_text = code_block(source, "captured-log")
    decoder, shown, at = json.JSONDecoder(), [], 0
    while shown_text[at:].strip():
        at += len(shown_text[at:]) - len(shown_text[at:].lstrip())
        record, at = decoder.raw_decode(shown_text, at)
        shown.append(record)
    assert [record["kind"] for record in shown] == [
        "action",
        "action",
        "action",
        "undo",
        "undo",
        "undo",
    ]

    # The browser's command: what it posts, before the door stamps anything.
    command_fields = ("kind", "revision", "widget", "action", "detail", "attempt")
    ids = {}
    with service_model.PageTransaction(page_dir) as page:
        for record in shown:
            command = {k: record[k] for k in command_fields if k in record}
            if "undoes" in record:
                command["undoes"] = ids[record["undoes"]]
            accepted, _ = event_contracts_model.append_admitted(
                page, {**command, "author": "user"}
            )
            ids[record["id"]] = accepted["id"]
    stored = events_model.read_events(page_dir)[1:]
    # The shown ids and times stand in for the replay's own, which are fresh.
    comparable = [
        {
            **replayed,
            "id": record["id"],
            "ts": record["ts"],
            **({"undoes": record["undoes"]} if "undoes" in record else {}),
        }
        for replayed, record in zip(stored, shown, strict=True)
    ]
    assert comparable == shown, (
        "the door now stores these records; paste them into #captured-log:\n"
        + shown_log(comparable)
    )
    assert shown_text.rstrip("\n") == shown_log(shown)

    # Each note sits under the last line of what it describes, so it is placed by
    # the record layout rather than by hand: pasted records that shift the lines
    # fail here with the lines to write instead.
    lines = shown_text.rstrip("\n").split("\n")
    starts = [n for n, line in enumerate(lines, 1) if line.startswith("{")]

    def last_line(record: int) -> int:
        return starts[record + 1] - 1 if record + 1 < len(starts) else len(lines)

    def line_of(record: int, key: str) -> int:
        """The line `key` opens in the `record`th shown record; `shown_log` starts a
        line at each object-valued field and at `id`."""
        [found] = [
            n
            for n in range(starts[record], last_line(record) + 1)
            if lines[n - 1].lstrip().startswith(f'"{key}": ')
        ]
        return found

    answered = next(
        n for n, record in enumerate(shown) if "answer" in record.get("meaning", {})
    )
    undo = next(n for n, record in enumerate(shown) if record["kind"] == "undo")
    # `attention` opens the line after the group `meaning` closes.
    expected = [
        starts[0],  # what the browser sent, from the record's first line
        line_of(0, "attention") - 1,  # stamped meaning, under its last line
        line_of(0, "id"),  # the minted id and seq
        line_of(answered, "attention") - 1,  # the answer closes that record's meaning
        last_line(undo),  # an undo, under its last line
    ]
    notes = source.tree.select("lf-code#captured-log > lf-note")
    assert '"answer": ' in lines[expected[3] - 1]
    assert [int(note.attrs["at"]) for note in notes] == expected, (
        f"place #captured-log's notes at {expected}"
    )


def test_the_event_log_page_quotes_the_registry():
    """The declaration the page annotates is `lf-options`' own."""
    source = SourceDocument(EVENT_LOG.read_text())
    entry = json.loads((DEFAULT_PACKAGE / "registry.json").read_text())["lf-options"]
    shown = json.loads("{" + code_block(source, "options-verbs") + "}")
    assert shown == {
        "x-state": entry["x-state"],
        "x-awaits": {
            "value": entry["x-awaits"]["value"],
            "answered": entry["x-awaits"]["answered"],
        },
    }


def test_every_command_the_docs_show_is_one_leaf_has():
    """A shown command is a promise the user will type it.

    The pages narrate the agent's half of the loop and `how-it-works.html` now shows
    it, and a renamed subcommand is what quietly breaks that: the transcript is prose
    to every other gate here, so a stale command would go on being published
    indefinitely. The names are resolved against click's own tree rather than listed
    in this file, because a list here is a second copy of the command surface and goes
    stale the same way the page does.
    """

    def shown_in(tree):
        """Prompt lines inside a transcript, and the inline mentions in the prose."""
        for block in tree.select("pre"):
            yield from re.findall(r"^\$ +leaf +(.+)$", block.text, re.MULTILINE)
        for code in tree.select(":not(pre) > code"):
            if found := re.fullmatch(r"leaf +(.+)", code.text, re.DOTALL):
                yield found.group(1)

    shown = [
        (source.name, line)
        for source in sorted(DOCS.glob("*.html"))
        for line in shown_in(SourceDocument(authored_markup(source)).tree)
    ]
    assert len(shown) > 10, (
        f"only {len(shown)} leaf commands found in the docs — the sweep is reading "
        f"past them rather than checking them"
    )

    def named(tokens):
        """The subcommand path these tokens walk from the root Click group."""
        command, path = cli_model.cli, []
        for token in tokens:
            if not isinstance(command, click.Group):
                break
            sub = command.get_command(None, token)
            if sub is None:
                break
            path.append(token)
            command = sub
        return path

    unknown = [
        f"{source}: leaf {line}"
        for source, line in shown
        if not named(shlex.split(line))
    ]
    assert not unknown, "these pages show commands leaf hasn't got:\n  " + "\n  ".join(
        unknown
    )
