"""The product pages are Leaf documents using the site's composed vocabulary."""

import html
import importlib.util
import json
import re
import shlex
import subprocess
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from jsonschema import Draft202012Validator
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf import session as session_model
from leaf.registry import validation as registry_validation
from leaf.registry.contract import event_clauses
from leaf.registry.storage import active_registry
from leaf.structure import SourceDocument
from leaf.validation import compatibility as validation_model
from PIL import Image

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "skills" / "leaf" / "assets"
DEFAULT_PACKAGE = ROOT / "skills" / "leaf" / "packages" / "default"
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
DEVELOPER_PAGES = tuple(sorted((EXAMPLES / "developer").glob("*.html")))

_record_demo_spec = importlib.util.spec_from_file_location(
    "record_demo", ROOT / "scripts" / "record-demo.py"
)
record_demo = importlib.util.module_from_spec(_record_demo_spec)
_record_demo_spec.loader.exec_module(record_demo)


def test_kernel_event_contracts_declare_closed_records():
    events = json.loads((ASSETS / "registry.json").read_text())["$events"]["kinds"]
    assert events
    envelope = {"id", "ts", "author", "kind", "seq"}
    for kind, contract in events.items():
        for schema in contract.values():
            Draft202012Validator.check_schema(schema)
        record = contract["record"]
        properties = record["properties"]
        assert record["type"] == "object"
        assert record["additionalProperties"] is False
        assert properties["kind"] == {"const": kind}
        assert envelope <= set(properties)
        assert envelope <= set(record["required"])


def test_docs_pages_leave_delivery_markup_to_leaf():
    pages = sorted(DOCS.glob("*.html"))
    assert {page.name for page in pages} == {
        "index.html",
        "examples.html",
        "extending.html",
        "how-it-works.html",
        "registry.html",
        "event-log.html",
    }
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
            for meta in parsed.named_metas
            if meta["name"] == "description"
        ]
        assert parsed.title.strip(), page.name
        assert len(described) == 1, page.name
        assert described[0].strip(), page.name
        descriptions[page.name] = described[0]
    # A description repeated across pages tells a user nothing about which one
    # they found, and search engines fold the duplicates together.
    assert len(set(descriptions.values())) == len(descriptions)


def test_docs_pages_use_only_registered_widgets():
    package_names = json.loads((ROOT / "examples" / "layer.json").read_text())
    registries = [
        ASSETS / "registry.json",
        DEFAULT_PACKAGE / "registry.json",
        *(
            ROOT / "skills" / "leaf" / "packages" / name / "registry.json"
            for name in package_names
        ),
        DOCS / "package" / "registry.json",
    ]
    registry = {}
    for source in registries:
        if source.exists():
            registry.update(json.loads(source.read_text()))
    used = {
        tag
        for page in DOCS.glob("*.html")
        for tag in re.findall(r"<(lf-[a-z-]+)", page.read_text())
    }
    assert used and used <= set(registry)


def test_every_product_page_has_the_same_site_navigation():
    expected = [
        ("/", "leaf"),
        ("/examples/", "Examples"),
        ("/how-it-works/", "How it works"),
        ("/extending/", "Extending"),
        ("https://github.com/max-sixty/leaf", "GitHub"),
    ]
    for source in sorted(DOCS.glob("*.html")):
        text = source.read_text()
        nav = re.search(r'<nav class="sitenav"[^>]*>(.*?)</nav>', text, re.DOTALL)
        assert nav, source.name
        assert re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', nav.group(1)) == (
            expected
        ), source.name


def test_extension_references_follow_the_concepts_they_explain():
    extending = (DOCS / "extending.html").read_text()
    how_it_works = (DOCS / "how-it-works.html").read_text()
    registry = (DOCS / "registry.html").read_text()
    assert 'href="/registry/"' in extending
    assert '<a href="/registry/">registry</a>' in how_it_works
    assert 'href="/extending/"' in registry
    assert 'href="/event-log/"' in extending
    assert '<a href="/event-log/">event log</a>' in how_it_works


def test_package_catalog_routes_every_optional_package_to_inspectable_content():
    extending = (DOCS / "extending.html").read_text()
    catalog = re.findall(
        r'<a\s+class="package-card"\s+href="([^"]+)"\s*>\s*<strong>([^<]+)</strong>',
        extending,
    )
    declared = json.loads((EXAMPLES / "layer.json").read_text())

    # Gallery is the core page's own browser-test package rather than a product
    # package. Every package a user can opt into gets one catalog entry.
    assert [name.casefold().replace(" ", "-") for _, name in catalog] == [
        name for name in declared if name != "gallery"
    ]
    for href, _ in catalog:
        if href.startswith("/examples/"):
            assert href.endswith("/")
        else:
            source_prefix = "https://github.com/max-sixty/leaf/blob/main/"
            assert href.startswith(source_prefix)
            assert (ROOT / href.removeprefix(source_prefix)).is_file()


def test_package_tutorial_registry_entry_is_valid(page_dir):
    blocks = re.findall(
        r"<pre[^>]*><code[^>]*>(.*?)</code></pre>",
        (DOCS / "extending.html").read_text(),
        re.DOTALL,
    )
    entry = json.loads(
        html.unescape(next(block for block in blocks if block.lstrip().startswith("{")))
    )
    registry = json.loads((page_dir / "registry.json").read_text()) | entry

    registry_validation.validate_registry(registry, "package tutorial")
    validation_model.validate_registry_examples(registry, "package tutorial")


def test_how_it_works_quotes_the_real_check_and_stamp_lines(page_dir):
    """Both lines the transcript shows an agent, taken from the commands themselves.

    A shown line is a promise about what the user will see. The changelog is the
    page's own, so the stamp line is generated here with the transcript's text
    rather than pattern-matched — a renamed field or a changed separator has to be
    written into the page before this passes again.
    """
    checked = CliRunner().invoke(cli_model.cli, ["version", "check", str(page_dir)])
    assert checked.exit_code == 0, checked.output
    success = next(
        line for line in checked.output.splitlines() if line.startswith("✓ index.html:")
    )

    changelog = "Two ways to shed load — which?"
    stamped = CliRunner().invoke(
        cli_model.cli, ["version", "stamp", str(page_dir), "--text", changelog]
    )
    assert stamped.exit_code == 0, stamped.output

    transcript = html.unescape((DOCS / "how-it-works.html").read_text())
    assert success in transcript
    assert stamped.output.strip() in transcript


def test_how_it_works_delivery_has_the_shape_a_real_delivery_has(page_dir):
    """The captured envelope is hand-copied, so it carries what a delivery carries now.

    A batch names each conversation its events land in, with that conversation's
    metadata, and the page's sample once kept an empty list beside a comment that
    opened one. The entry keys are read off a delivery frozen here rather than
    listed, so a field the envelope gains has to be written into the page too. Each
    event's handling is the text the shipped layer delivers for it today, so a
    reworded clause has to be copied into the sample.
    """
    transcript = html.unescape((DOCS / "how-it-works.html").read_text())
    # The page indents the envelope for reading, so it opens on a line of its own.
    shown, _ = json.JSONDecoder().raw_decode(transcript, transcript.index("\n{\n") + 1)
    assert shown["format"] == delivery_model.DELIVERY_FORMAT
    comment = events_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    with service_model.PageTransaction(page_dir) as page:
        stored = next(event for event in page.events if event["id"] == comment["id"])
        real = delivery_model.freeze_delivery(
            [delivery_model.batch_data(page_dir, page, [stored])],
            carrier="wait",
            acknowledge=session_model.wait_acknowledgement(None),
        )
    # The transcript is Claude Code's direct loop, so its acknowledgement is the
    # one `leaf wait` writes there, addressed to the envelope's own id.
    assert shown.keys() == real.keys()
    assert shown["carrier"] == real["carrier"]
    assert shown["acknowledge"] == real["acknowledge"].replace(real["id"], shown["id"])
    [real_batch] = real["batches"]
    (real_conversation,) = real_batch["conversations"]
    registry = active_registry(page_dir)

    for batch in shown["batches"]:
        assert batch.keys() == real_batch.keys()
        named = [c for event in batch["events"] for c in event["conversations"]]
        assert [c["id"] for c in batch["conversations"]] == list(dict.fromkeys(named))
        for conversation in batch["conversations"]:
            assert conversation.keys() == real_conversation.keys()
        digests = {c["id"]: c for c in batch["conversations"]}
        for event in batch["events"]:
            shown_clauses = [batch["handling"][h] for h in event["handling"]]
            # A clause reads the event's conversation beside the event.
            case = dict(event)
            if event["conversations"]:
                case["conversation"] = digests[event["conversations"][0]]
            told = event_clauses(case, registry)
            delivered = [c["text"] for c in told]
            assert shown_clauses == delivered, event["id"]


EVENT_LOG = DOCS / "event-log.html"


def code_block(source: str, block_id: str) -> str:
    """The unescaped body of one authored `lf-code`'s `<pre>`."""
    found = re.search(
        rf'<lf-code id="{block_id}"[^>]*>\s*<pre>\n?(.*?)</pre>', source, re.DOTALL
    )
    assert found, block_id
    return html.unescape(found.group(1))


def shown_log(records: list[dict]) -> str:
    """Stored records as the event-log page prints them: each record's JSON as
    `leaf events` writes it, broken before and after each object-valued field and
    before `id`, so a record reads in a few lines rather than one wide one. An
    object too long for one line puts each of its members on a line of its own."""
    width = 96

    def field(key, value):
        line = f"{json.dumps(key)}: {json.dumps(value)}"
        if not isinstance(value, dict) or len(line) <= width:
            return line
        members = [f"{json.dumps(k)}: {json.dumps(v)}" for k, v in value.items()]
        return f"{json.dumps(key)}: {{" + ",\n   ".join(members) + "}"

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
    """The page's log was captured from its own specimen driven in a browser. The
    commands it records go back through the append door on the same markup, and
    what the door stores now has to be what the page shows, `id` and `ts` aside.
    A changed field, meaning, or refusal fails here with the records to paste."""
    source = EVENT_LOG.read_text()
    template = re.search(
        r'<template id="try-page" data-specimen>(.*?)</template>', source, re.DOTALL
    )
    assert template
    (page_dir / "index.html").write_text(
        '<!doctype html><html lang="en"><head><title>Release question</title>'
        '<meta name="description" content="The specimen."></head>'
        f"<body><main>{template.group(1)}</main></body></html>"
    )
    stamped = CliRunner().invoke(
        cli_model.cli, ["version", "stamp", str(page_dir), "--text", "v1"]
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
            accepted = event_contracts_model.append_admitted(
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
    # `id` opens the line after the group `meaning` closes.
    expected = [
        starts[0],  # what the browser sent, from the record's first line
        line_of(0, "id") - 1,  # the stamped meaning, under its last line
        line_of(0, "id"),  # the minted id and seq
        line_of(answered, "id") - 1,  # the answer, which closes that record's meaning
        last_line(undo),  # an undo, under its last line
    ]
    notes = re.search(
        r'<lf-code id="captured-log".*?</pre>(.*?)</lf-code>', source, re.DOTALL
    )
    assert notes
    assert '"answer": ' in lines[expected[3] - 1]
    assert [int(at) for at in re.findall(r'<lf-note at="(\d+)"', notes.group(1))] == (
        expected
    ), f"place #captured-log's notes at {expected}"


def record(verb_state: dict) -> str:
    """What the page's verb table says a verb's standing state reads as in markup."""
    if "creates" in verb_state:
        return f"creates an <code>{verb_state['creates']['child']}</code>"
    shape = verb_state.get("record")
    if shape is None:
        return "none"
    if shape["kind"] == "position":
        return f"position in an <code>{shape['within']}</code>"
    if shape["kind"] == "body":
        return "body"
    written = ", written by the agent" if verb_state.get("writer") == "agent" else ""
    return f"<code>{shape['attr']}</code> attribute{written}"


def test_the_event_log_page_quotes_the_registry():
    """The declaration the page annotates is `lf-options`' own, and its table of
    verbs is every verb the kernel and bundled packages declare, each with the
    unit and markup record its declaration gives it."""
    source = EVENT_LOG.read_text()
    entry = json.loads((DEFAULT_PACKAGE / "registry.json").read_text())["lf-options"]
    shown = json.loads("{" + code_block(source, "options-verbs") + "}")
    assert shown == {
        "x-state": entry["x-state"],
        "x-awaits": {"answered": entry["x-awaits"]["answered"]},
    }

    registries = [
        ASSETS / "registry.json",
        *sorted((ROOT / "skills" / "leaf" / "packages").glob("*/registry.json")),
    ]
    declared = sorted(
        (
            f"<code>{tag}</code>",
            f"<code>{verb}</code>",
            verb_state["unit"],
            record(verb_state),
        )
        for path in registries
        for tag, element in json.loads(path.read_text()).items()
        if tag.startswith("lf-")
        for verb, verb_state in element.get("x-state", {}).items()
    )
    table = re.search(
        r'<table id="all-verbs">.*?<tbody>(.*?)</tbody>', source, re.DOTALL
    )
    assert table
    rows = [
        tuple(
            " ".join(cell.split())
            for cell in re.findall(r"<td>(.*?)</td>", row, re.DOTALL)
        )
        for row in re.findall(r"<tr>(.*?)</tr>", table.group(1), re.DOTALL)
    ]
    assert sorted(rows) == declared


def test_every_command_the_docs_show_is_one_leaf_has():
    """A shown command is a promise the user will type it.

    The pages narrate the agent's half of the loop and `how-it-works.html` now shows
    it, and a renamed subcommand is what quietly breaks that: the transcript is prose
    to every other gate here, so a stale command would go on being published
    indefinitely. The names are resolved against click's own tree rather than listed
    in this file, because a list here is a second copy of the command surface and goes
    stale the same way the page does.
    """

    def shown_in(text):
        """Prompt lines inside a transcript, and the inline mentions in the prose.

        A block's own tags sit on its first and last lines — `<pre><code>$ leaf …`
        and `… 3</code></pre>` — so the markup comes out before the lines are read,
        or the sweep silently skips the first command it was written for.
        """
        for block in re.findall(r"<pre[^>]*>(.*?)</pre>", text, re.DOTALL):
            yield from re.findall(
                r"^\$ +leaf +(.+)$", re.sub(r"<[^>]+>", "", block), re.MULTILINE
            )
        yield from re.findall(r"<code>leaf +([^<]+)</code>", text)

    shown = [
        (source.name, line)
        for source in sorted(DOCS.glob("*.html"))
        for line in shown_in(html.unescape(source.read_text()))
    ]
    assert len(shown) > 10, (
        f"only {len(shown)} leaf commands found in the docs — the sweep is reading "
        f"past them rather than checking them"
    )

    def named(tokens):
        """The subcommand path these tokens walk, greedily, from the root group."""
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


def test_demo_waiter_preserves_the_reason_a_wait_delivered_nothing():
    class FailedWait:
        returncode = 2

        def communicate(self, *, timeout):
            assert timeout == 10
            return "", "the page closed while waiting\n"

    waiter = object.__new__(record_demo.DemoWaiter)
    waiter.process = FailedWait()

    with pytest.raises(
        RuntimeError,
        match="the demo waiter exited 2 with 0 page batches instead of one\\n"
        "the page closed while waiting",
    ):
        waiter.receive()


@pytest.mark.nightly
def test_demo_recording_drives_the_browser_journey(tmp_path):
    output = tmp_path / "demo.gif"
    # Not check=True: with the streams captured, the CalledProcessError it raises
    # names the command and the exit status and takes both of them down with it,
    # so a browser step that timed out and a server that never bound report the
    # same nothing. This is `open_page`'s complaint about "Failed to load
    # resource" one file over — carry what failed into the failure.
    recorded = subprocess.run(
        [ROOT / "scripts" / "record-demo.sh", "--output", output],
        capture_output=True,
        text=True,
        check=False,
    )

    assert recorded.returncode == 0, (
        f"record-demo.sh exited {recorded.returncode}\n"
        f"{recorded.stdout}{recorded.stderr}".rstrip()
    )
    assert recorded.stdout.strip() == f"Recorded {output}"
    assert output.read_bytes().startswith(b"GIF89a")
    # One staged scene, photographed for each surface that shows it: the landing
    # page's figure in both schemes, and the card, at the 1.91:1 an unfurler draws.
    # Shot at that shape rather than cropped to it, so the banner survives the trip.
    for name, size in (
        ("session-light.png", (1280, 953)),
        ("session-dark.png", (1280, 953)),
        ("session-card.png", (1200, 630)),
    ):
        with Image.open(output.parent / name) as still:
            assert still.size == size, name
