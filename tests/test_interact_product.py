"""Version corpus, catalog, message, and export tests."""

import importlib.util
import json
import os
import re
import shutil
from pathlib import Path

from click.testing import CliRunner
from interact_support import (
    COMMAND_HUB_PACKAGE,
    PAGE,
    ROOT,
    _report,
    _tasks_version,
    check,
    comment,
    fetch,
    fragment_errors,
    link_command_hub_package,
    live_versions,
    page_state,
    publish,
    published,
)
from leaf import checking as checking_model
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import events as events_model
from leaf import files as files_model
from leaf import layer as layer_model
from leaf import registry as registry_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import validation as validation_model


def test_versions_publish_only_once_noted(page_dir):
    assert live_versions(page_dir) == []
    assert page_state(page_dir)["versions"] == []
    result = CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "first cut"],
    )
    assert result.exit_code == 0, result.output
    assert live_versions(page_dir) == [1]
    # The next version stays unpublished until its own note lands.
    (page_dir / "versions" / "v2.html").write_text(PAGE)
    assert live_versions(page_dir) == [1]


def test_versions_run_in_number_order_past_v9(page_dir):
    """Everything downstream reads "the latest version" off the end of this list —
    what `version publish` exposes, what the server projects at the live root, what
    `version check` diffs the new version with. Sorted as names, v10 would land
    before v2 and every one of those would quietly answer with the wrong version."""
    for n in range(2, 12):
        (page_dir / "versions" / f"v{n}.html").write_text(PAGE)
    assert files_model.list_versions(page_dir) == list(range(1, 12))
    for n in range(1, 12):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "version",
                "publish",
                str(page_dir),
                "--version",
                str(n),
                "--text",
                f"cut {n}",
            ],
        )
        assert result.exit_code == 0, result.output
    assert live_versions(page_dir) == list(range(1, 12))


def test_version_filenames_are_canonical(page_dir, server):
    """Only an ASCII, unpadded file can identify a positive version."""
    (page_dir / "versions" / "v01.html").write_text("<h1>shadow</h1>")
    (page_dir / "versions" / "v1٢.html").write_text("<h1>Unicode alias</h1>")
    (page_dir / "versions" / "v2.html").mkdir()
    assert files_model.list_versions(page_dir) == [1]
    assert check(page_dir, version=1).exit_code == 0
    assert fetch(f"{server}/versions/v01.html")[0] == 404


def test_choose_requires_an_id(page_dir):
    # Actions name their widget by id, so an interactive group can't go without one.
    registry = registry_model.load_registry(page_dir)
    errs = fragment_errors(
        '<lf-options choose><lf-option id="o1"><strong>A</strong></lf-option></lf-options>',
        registry,
    )
    assert errs and "'id' is a dependency of 'choose'" in " ".join(errs)


def test_specimen_admits_interactive_widgets(page_dir):
    # The registry marks a specimen's content quoted; the runtime leaves the
    # interactive widgets inside unwired. Validation is unchanged by the
    # wrapper: nesting rules (lf-option under lf-options) still hold.
    registry = registry_model.load_registry(page_dir)
    errs = fragment_errors(
        '<lf-specimen id="sp" label="a decision">'
        '<lf-options id="g" choose><lf-option id="o1"><strong>A</strong></lf-option></lf-options>'
        '<lf-board id="b"><lf-column id="c" label="To do">'
        '<lf-card id="k"><strong>Card</strong></lf-card></lf-column></lf-board>'
        "</lf-specimen>",
        registry,
    )
    assert errs == []


def test_an_ask_region_frames_exactly_one_request(page_dir):
    """A broad Ask has one source of liveness and state; zero leaves navigation
    pointing at nothing, while two make its answer and roll-up ownership ambiguous."""
    registry = registry_model.load_registry(page_dir)
    first = (
        '<lf-options id="g-one" choose>'
        '<lf-option id="o-one"><strong>One</strong></lf-option>'
        "</lf-options>"
    )
    second = (
        '<lf-options id="g-two" choose>'
        '<lf-option id="o-two"><strong>Two</strong></lf-option>'
        "</lf-options>"
    )

    assert (
        fragment_errors(
            f'<lf-ask id="ask-one"><h2>Choose</h2><p>Context.</p>{first}</lf-ask>',
            registry,
        )
        == []
    )

    # Evidence can quote another request-shaped widget without giving this Ask a
    # second live source. The runtime already excludes x-exhibit descendants from the
    # Ask list, so the authored boundary must read the same relation.
    with_evidence = (
        '<lf-ask id="ask-with-evidence"><h2>Choose</h2>'
        f'{first}<lf-specimen id="request-example" label="another request">'
        f"{second}</lf-specimen></lf-ask>"
    )
    assert fragment_errors(with_evidence, registry) == []

    empty = fragment_errors(
        '<lf-ask id="ask-empty"><h2>Nothing to answer</h2></lf-ask>', registry
    )
    assert "an Ask must frame exactly one x-awaits widget, found none" in " ".join(
        empty
    )

    crowded = fragment_errors(
        f'<lf-ask id="ask-crowded">{first}{second}</lf-ask>', registry
    )
    message = " ".join(crowded)
    assert "an Ask must frame exactly one x-awaits widget" in message
    assert "<lf-options#g-one>" in message and "<lf-options#g-two>" in message


def test_settling_a_decision_drops_no_ids(page_dir):
    """Retiring a settled decision is a collapse, not a deletion — which is the
    whole reason it's expressible: `version check` forbids dropping an id, and
    the alternatives behind the disclosure keep both their ids and the anchors
    on them. A group can't be settled without an id either; the reader's
    open/closed state is remembered against it."""
    registry = registry_model.load_registry(page_dir)
    assert "'id' is a dependency of 'settled'" in " ".join(
        fragment_errors(
            '<lf-options settled><lf-option id="o1"><strong>A</strong></lf-option></lf-options>',
            registry,
        )
    )

    group = '<lf-options id="pick" choose{}><lf-option id="opt-a"{}><strong>A</strong></lf-option>'
    group += '<lf-option id="opt-b"><strong>B</strong></lf-option></lf-options>'
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("</main>", group.format("", "") + "</main>")
    )
    publish(page_dir)
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace("</main>", group.format(" settled", " chosen") + "</main>")
    )
    assert checking_model.cmd_check(page_dir, 2) == 0

    # Deleting the alternatives instead is what check is there to stop.
    (page_dir / "versions" / "v2.html").write_text(PAGE)
    assert checking_model.cmd_check(page_dir, 2) == 1


def test_registry_examples_validate(page_dir):
    registry = registry_model.load_registry(page_dir)
    assert any(
        tag.startswith("lf-") and "x-example" in entry
        for tag, entry in registry.items()
    )
    assert (
        validation_model.validate_registry_examples(registry, "vendored registry")
        is registry
    )


def test_registry_example_ids_are_independent_between_entries(page_dir):
    registry = registry_model.load_registry(page_dir)
    registry["lf-diff"]["x-example"] = (
        '<lf-diff id="shared"><pre>one changed line</pre></lf-diff>'
    )
    registry["lf-tree"]["x-example"] = (
        '<lf-tree id="shared"><pre>one/file.py</pre></lf-tree>'
    )

    assert (
        validation_model.validate_registry_examples(registry, "independent examples")
        is registry
    )


def test_every_path_a_diff_resolves_names_a_language_the_bundle_carries(page_dir):
    """The language vocabulary has two halves and they have to agree. `names` is the half
    an author writes and the half scripts/vendor-highlight.sh builds the tokenizer bundle
    from; `paths` is what a filename means, which is how a diff colours a file nobody
    declared a language for. A path resolving outside `names` would resolve to a language
    the vendored bundle doesn't carry, and the whole hunk would fall back to plain text
    with a console error — visible only on a page that happens to diff that extension."""
    reg = json.loads((page_dir / "registry.json").read_text())
    names = set(reg["$languages"]["names"])
    paths = reg["$languages"]["paths"]
    assert (
        paths
    )  # a table with nothing in it would pass the check below and colour nothing
    assert set(paths.values()) <= names, (
        f"no bundle for {sorted(set(paths.values()) - names)}"
    )


def test_examples_pass_check(tmp_path, monkeypatch):
    """Every gallery page in examples/ lints clean against the shipped layer."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    root = Path(__file__).parent.parent / "examples"
    packages = json.loads((root / "layer.json").read_text(encoding="utf-8"))
    link_command_hub_package(tmp_path)
    examples = sorted(root.glob("*.html"))
    assert examples
    selection_args = [arg for package in packages for arg in ("--package", package)]
    for example in examples:
        d = tmp_path / example.stem
        initialized = CliRunner().invoke(
            cli_model.cli, ["page", "init", *selection_args, str(d)]
        )
        assert initialized.exit_code == 0, f"{example.name}: {initialized.output}"
        (d / "versions" / "v1.html").write_text(example.read_text())
        shutil.copytree(ROOT / "examples" / "media", d / "media", dirs_exist_ok=True)
        # The example's companion log, where it ships one (examples/CLAUDE.md), so
        # the lint reads the page under the state its own log puts on it.
        seed = example.with_suffix(".jsonl")
        if seed.exists():
            (d / "comments.jsonl").write_text(seed.read_text(encoding="utf-8"))
        data_seed = example.with_suffix(".data.json")
        if data_seed.exists():
            for name, value in json.loads(
                data_seed.read_text(encoding="utf-8")
            ).items():
                data_model.cmd_data_set(d, name, value)
        result = check(d)
        assert result.exit_code == 0, f"{example.name}: {result.output}"


def test_every_widget_in_the_vocabulary_stands_in_an_example():
    """Eight sweeps in test_render.py read a widget inside a whole page, and their
    corpus is examples/, so a widget no example holds is one none of the eight has ever
    seen — a gap that reads as coverage, since the widget's own tests are green.
    lf-shot and lf-specimen were outside them from the day each was written.
    examples/CLAUDE.md carries the rest, including the shapes this floor doesn't
    reach."""
    registry = validation_model.incoming_registry(
        [
            schema_model.ASSETS,
            schema_model.DEFAULT_PACKAGE,
            COMMAND_HUB_PACKAGE,
        ]
    )
    # The gallery is generated from the others, so it can only repeat their coverage.
    authored = " ".join(
        p.read_text()
        for p in (ROOT / "examples").glob("*.html")
        if p.name != "gallery.html"
    )
    tags = [tag for tag in registry if not tag.startswith("$")]
    assert tags, "no widgets read — an empty vocabulary demonstrates itself"
    undemonstrated = [tag for tag in tags if not re.search(rf"<{tag}[\s>]", authored)]
    assert not undemonstrated, (
        f"no example holds {', '.join(undemonstrated)} — see examples/CLAUDE.md"
    )


def test_gallery_is_generated_from_the_examples():
    """examples/gallery.html is derived; a commit that lets it drift fails here."""
    spec = importlib.util.spec_from_file_location(
        "gallery", Path(__file__).parent.parent / "scripts" / "gallery.py"
    )
    gallery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gallery)
    committed = (Path(__file__).parent.parent / "examples" / "gallery.html").read_text()
    assert gallery.build() == committed, "examples changed — rerun scripts/gallery.py"
    committed_data = json.loads(
        (Path(__file__).parent.parent / "examples" / "gallery.data.json").read_text()
    )
    assert gallery.build_data() == committed_data, (
        "example data changed — rerun scripts/gallery.py"
    )


def test_the_key_table_is_generated_from_the_registry():
    """docs/packages.html's table of x- keys is written from the registry's $keys —
    one home for what a key means, read by the catalog and the site alike — so a
    commit that lets the two drift fails here. Compared with the whitespace between
    tags dropped, because prettier re-flows the page and a formatter's line breaks are
    not what the table says."""
    spec = importlib.util.spec_from_file_location(
        "keydocs", Path(__file__).parent.parent / "scripts" / "keydocs.py"
    )
    keydocs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(keydocs)
    committed = keydocs.DOCS_PAGE.read_text()

    def said(html):
        return re.sub("\\s+", " ", re.sub("\\s*(<[^>]*>)\\s*", "\\1", html))

    assert said(keydocs.build(committed)) == said(committed), (
        "the registry's $keys changed — rerun scripts/keydocs.py"
    )
    # And that the region holds a row for every key the registry documents.
    keys = json.loads(schema_model.ASSETS.joinpath("registry.json").read_text())[
        "$keys"
    ]
    for key in keys:
        if key != "description":
            assert f"<td><code>{key}</code></td>" in said(committed), key


def test_no_example_writes_another_example_s_sentences():
    """Each page's connective prose is written in its own subject.

    The gesture is shared vocabulary — every board takes a drag, every group takes a
    pick, and the words for those are meant to repeat. The sentence around the gesture
    is not: a page that borrows one is describing another page's work in that page's
    words, and the corpus is the one place a reader sees them side by side.

    A batch of them got in at once, and the cause was upstream of the corpus.
    references/page-authoring.md's "Interactivity and evidence" entry quoted two model
    sentences, and both reached shipped examples word for word; a phrase sitting ready
    to paste is a phrase that gets pasted. That entry now names what the sentence must
    carry instead, and this is what says whether it worked.

    Twelve words, from a measurement rather than a guess: with those rewritten, the
    longest run any two examples share is seven, and nothing at all is shared at eight.
    Both sevens are between pages this change never touched: the guarantee a version
    makes about a board, and a fictional detail two pages were written to share. So
    twelve leaves five words of room over what the corpus legitimately repeats, and is
    loose enough to let a single borrowed clause through — which is the judgement the
    skill entry carries and a word count cannot."""
    run = 12
    examples = {
        p.stem: p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "examples").glob("*.html"))
        # gallery.html embeds every sibling verbatim, so it shares everything by
        # construction; scripts/gallery.py is what holds it true.
        if p.stem != "gallery"
    }
    assert len(examples) > 1, examples

    def words(html: str) -> list[str]:
        # <main> only: the <head>'s CSP meta is identical in every one by requirement.
        body = html[html.index("<main>") + len("<main>") : html.rindex("</main>")]
        return re.findall(r"[a-z0-9']+", re.sub(r"<[^>]+>", " ", body).lower())

    seen: dict[tuple, str] = {}
    shared: list[str] = []
    for name, html in examples.items():
        ws = words(html)
        for i in range(len(ws) - run + 1):
            gram = tuple(ws[i : i + run])
            if gram in seen and seen[gram] != name:
                shared.append(f"{seen[gram]} and {name}: {' '.join(gram)}")
            seen.setdefault(gram, name)
    assert not shared, (
        f"{len(shared)} run(s) of {run}+ words shared between examples; write each "
        "page's own sentence:\n  " + "\n  ".join(sorted(set(shared))[:10])
    )


def test_catalog_prints_widgets_and_idioms(page_dir):
    result = CliRunner().invoke(cli_model.cli, ["page", "catalog", str(page_dir)])
    assert result.exit_code == 0
    assert "lf-options" in result.output
    assert "x-example" in result.output
    assert ".callout" in result.output
    assert "$idioms" not in result.output  # sections are split out, not dumped raw
    # Every x- key an entry may declare is explained, in the one section that does.
    assert "# The x- keys an entry may declare" in result.output
    for key in schema_model.EXTENSION_SCHEMA["properties"]:
        assert f'"{key}": "' in result.output, key


def test_catalog_prints_a_dollar_key_it_was_never_taught(page_dir):
    """The catalog is what the agent authors from, and a layer declaring a $ fact of
    its own is the documented way to share one — so a catalog working from a list of $
    names it had been taught dropped exactly what a project had gone to the trouble of
    declaring, silently, in the one output that would have shown it. Same never-closed
    rule as the widget list, one side of the registry over."""
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["$hazards"] = {"freeze": {"description": "Deploys freeze on Fridays."}}
    registry_path.write_text(json.dumps(registry))

    result = CliRunner().invoke(cli_model.cli, ["page", "catalog", str(page_dir)])

    assert result.exit_code == 0, result.output
    assert "Deploys freeze on Fridays." in result.output
    assert "# $hazards, declared by this layer." in result.output
    # The runtime contract and the vendoring record stay out of the author's catalog.
    assert '"$events"' not in result.output


def test_reply_validates_widget_markup(page_dir):
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )

    def reply(markup):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "reply",
                str(page_dir),
                "--to",
                "c1",
                "--text",
                "See:",
                "--markup",
                markup,
            ],
        )

    bad = reply('<lf-diagram id="f"><pre>graph LR</pre><b>x</b></lf-diagram>')
    assert bad.exit_code != 0
    assert "its body is one <pre> holding the text" in bad.output
    duplicate = reply(
        '<lf-diagram id="browser-id" id="file-id"><pre>graph LR\nA --> B</pre></lf-diagram>'
    )
    assert duplicate.exit_code != 0
    assert "duplicate attribute" in duplicate.output
    # Prose belongs in --text, where it renders as Markdown; a markup field
    # holding none is a wrong turn, not an empty widget list.
    prose = reply("just words")
    assert prose.exit_code != 0
    assert "carries no widget" in prose.output
    good = reply('<lf-diagram id="f"><pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>')
    assert good.exit_code == 0, good.output
    event = events_model.read_events(page_dir)[-1]
    assert event["kind"] == "reply"
    assert event["author"] == "claude"
    assert event["text"] == "See:"
    assert event["markup"].startswith("<lf-diagram")


def test_widget_ids_are_one_universe_across_page_and_replies(page_dir):
    """The runtime resolves actions document-wide by id, so a reply widget must not
    reuse a page id — and a later version must not take a reply's."""
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )

    def reply(markup):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "reply",
                str(page_dir),
                "--to",
                "c1",
                "--text",
                "Pick:",
                "--markup",
                markup,
            ],
        )

    # `flow` is the page's lf-diagram id (PAGE fixture) — refused.
    clash = reply(
        '<lf-options id="flow" choose><lf-option id="o1"><strong>A</strong></lf-option></lf-options>'
    )
    assert clash.exit_code != 0 and "flow" in clash.output
    fresh = reply(
        '<lf-options id="q1" choose><lf-option id="q1-a"><strong>A</strong></lf-option></lf-options>'
    )
    assert fresh.exit_code == 0, fresh.output
    # A second reply can't reuse the first reply's ids either, nor its own within itself.
    again = reply(
        '<lf-options id="q1" choose><lf-option id="q1-b"><strong>B</strong></lf-option></lf-options>'
    )
    assert again.exit_code != 0 and "q1" in again.output
    selfdup = reply(
        '<lf-options id="q2" choose><lf-option id="q2"><strong>B</strong></lf-option></lf-options>'
    )
    assert selfdup.exit_code != 0 and "within itself" in selfdup.output
    # Text claims no ids however it quotes a tag — only the `markup` field does, and
    # a user's message never carries one (the log is append-only; a false claim
    # would deadlock every future version).
    events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": "c1",
            "text": 'why not <lf-diagram id="quoted"> here?',
        },
    )
    ok = reply(
        '<lf-options id="quoted" choose><lf-option id="quoted-a"><strong>A</strong></lf-option></lf-options>'
    )
    assert ok.exit_code == 0, ok.output
    # And a new version taking the reply's id fails check.
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace('<section id="plan">', '<section id="plan"><p id="q1">stolen</p>')
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert (
        "taken by widget markup in a reply" in result.output and "q1" in result.output
    )


def test_the_runtimes_lf_id_namespace_is_off_limits(page_dir):
    """leaf.js coins document ids under lf- for its own chrome — lf-composer-quote —
    and points ARIA at them. An authored id there would aim those references at the page
    instead, silently. One rule over both places an id can be authored: a version, and
    the widget markup in Claude's reply."""
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace(
            '<section id="plan">', '<section id="plan"><p id="lf-msg-7">mine</p>'
        )
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "lf- namespace" in result.output and "lf-msg-7" in result.output

    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    reply = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "Pick:",
            "--markup",
            '<lf-options id="lf-pick" choose><lf-option id="o1"><strong>A</strong></lf-option></lf-options>',
        ],
    )
    assert reply.exit_code != 0
    assert "lf- namespace" in reply.output and "lf-pick" in reply.output


# ---------- messages: text is Markdown for the browser, markup is the gate's ----------


def test_the_wire_ships_a_message_as_logged(page_dir):
    """The wire adds nothing to the log: text is Markdown the page's vendored runtime
    renders (test_render holds that side), markup is the fragment the CLI gate
    validated, and the only vocabulary a page's frozen layer has to keep speaking is
    the log's own, which $events stamps."""
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "text": "two things:\n\n- one\n- **two**",
        },
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "Fixed in `poll()`.",
            "--markup",
            '<lf-diagram id="fix"><pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>',
        ],
    )
    assert result.exit_code == 0, result.output
    wire = {e["kind"]: e for e in page_state(page_dir)["events"]}
    assert wire["comment"]["text"] == "two things:\n\n- one\n- **two**"
    assert "html" not in wire["comment"] and "html" not in wire["reply"]
    assert wire["reply"]["markup"].startswith("<lf-diagram")


def test_each_agent_session_posts_as_its_own_voice(page_dir, monkeypatch):
    """Several worker sessions report to one page. Each agent-authored event
    carries its poster's display name and session id from the poster's own
    environment, so the log tells the voices apart by id; the claim — the
    watcher the banner names — and every publication stay the hub's, untouched
    by a worker's post."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "hub")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    monkeypatch.setenv("LEAF_AGENT", "Hub")
    _tasks_version(page_dir, 1, "active")
    service_model.claim_page(page_dir)
    published(page_dir)
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "status?"}
    )

    def reply(text):
        return CliRunner().invoke(
            cli_model.cli, ["reply", str(page_dir), "--to", "c1", "--text", text]
        )

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0
    assert reply("indexing done").exit_code == 0
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-2")
    monkeypatch.setenv("LEAF_AGENT", "Crawler")
    assert reply("crawl running").exit_code == 0

    events = events_model.read_events(page_dir)
    notes = [e for e in events if e["kind"] == "note"]
    assert [(e["agent"], e["session"]) for e in notes] == [("Hub", "hub")]
    report = next(e for e in events if e["kind"] == "report")
    assert (report["agent"], report["session"]) == ("Indexer", "worker-1")
    replies = [e for e in events if e["kind"] == "reply"]
    assert [(e["agent"], e["session"]) for e in replies] == [
        ("Indexer", "worker-1"),
        ("Crawler", "worker-2"),
    ]
    session = service_model.page_claim(page_dir)
    assert session["id"] == "hub" and session["agent"] == "Hub"
    assert page_state(page_dir)["agent"] == "Hub"
    # The reader meets each message under the name it carried.
    transcript = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert "- **Indexer**: indexing done" in transcript.output
    assert "- **Crawler**: crawl running" in transcript.output


def test_an_agent_edits_its_own_messages_without_rewriting_history(
    page_dir, monkeypatch
):
    """An edit changes what the conversation says, not what the log said before it.

    Roots and replies are both messages, and the posting session is their authoring
    identity. The raw log therefore keeps each original and the revision as separate
    events, while every folded reading shows the latest words with an edited marker.
    Another agent session — and an agent looking at the reader's words — cannot revise
    speech that is not its own.
    """
    publish(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")

    opened = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(page_dir), "--text", "The index is still pending."],
    )
    assert opened.exit_code == 0, opened.output
    root = json.loads(opened.output)
    reader = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "reader-thread",
            "author": "user",
            "version": 1,
            "text": "What about the crawl?",
        },
    )
    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            reader["id"],
            "--text",
            "The crawl is paused.",
        ],
    )
    assert answered.exit_code == 0, answered.output
    reply = json.loads(answered.output)

    revisions = []
    for message, text in [
        (root, "The index is complete."),
        (root, "The index is complete and verified."),
        (reply, "The crawl is running."),
    ]:
        result = CliRunner().invoke(
            cli_model.cli,
            ["edit", str(page_dir), "--to", message["id"], "--text", text],
        )
        assert result.exit_code == 0, result.output
        revisions.append(json.loads(result.output))

    history_result = CliRunner().invoke(cli_model.cli, ["events", str(page_dir)])
    assert history_result.exit_code == 0, history_result.output
    events = [json.loads(line) for line in history_result.output.splitlines()]
    originals = {
        event["id"]: event for event in events if event["kind"] in {"comment", "reply"}
    }
    revision_events = [event for event in events if event["kind"] == "edit"]
    assert originals[root["id"]]["text"] == "The index is still pending."
    assert originals[reply["id"]]["text"] == "The crawl is paused."
    assert [(event["message"], event["text"]) for event in revisions] == [
        (root["id"], "The index is complete."),
        (root["id"], "The index is complete and verified."),
        (reply["id"], "The crawl is running."),
    ]

    state_result = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert state_result.exit_code == 0, state_result.output
    state = json.loads(state_result.output)
    folded = {
        message["id"]: message
        for thread in state["threads"]
        for message in thread["messages"]
    }
    latest_revision = {revision["message"]: revision for revision in revision_events}
    for message in (root, reply):
        revision = latest_revision[message["id"]]
        assert folded[message["id"]]["text"] == revision["text"]
        assert folded[message["id"]]["edited"] == {
            key: revision[key] for key in ("id", "seq", "ts")
        }

    transcript = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert transcript.exit_code == 0, transcript.output
    assert (
        "- **Indexer** *(edited)*: The index is complete and verified."
        in transcript.output
    )
    assert "- **Indexer** *(edited)*: The crawl is running." in transcript.output
    assert "still pending" not in transcript.output
    assert "crawl is paused" not in transcript.output

    before = events_model.read_events(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-2")
    monkeypatch.setenv("LEAF_AGENT", "Crawler")
    foreign = CliRunner().invoke(
        cli_model.cli,
        ["edit", str(page_dir), "--to", root["id"], "--text", "Taken over."],
    )
    assert foreign.exit_code != 0
    assert "belongs to agent session 'worker-1'" in foreign.output
    reader_edit = CliRunner().invoke(
        cli_model.cli,
        ["edit", str(page_dir), "--to", reader["id"], "--text", "Changed."],
    )
    assert reader_edit.exit_code != 0
    assert "is not agent-authored" in reader_edit.output
    assert events_model.read_events(page_dir) == before
    sessionless = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "version": 1,
            "text": "No recorded session owns this.",
        },
    )
    before_unidentified_edit = events_model.read_events(page_dir)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    unidentified = CliRunner().invoke(
        cli_model.cli,
        ["edit", str(page_dir), "--to", sessionless["id"], "--text", "Changed."],
    )
    assert unidentified.exit_code != 0
    assert "has no agent session identity" in unidentified.output
    assert before_unidentified_edit[-1]["id"] == sessionless["id"]
    assert events_model.read_events(page_dir) == before_unidentified_edit


def test_edit_refuses_a_page_vendored_before_its_event_contract(page_dir, monkeypatch):
    """A contract-bearing writer speaks only the vocabulary vendored into the page."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    message = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Indexer",
            "session": "worker-1",
            "version": 1,
            "text": "The old layer can render this message.",
        },
    )
    registry = files_model.read_json(page_dir / "registry.json")
    del registry["$events"]["kinds"]["edit"]
    files_model.write_json(page_dir / "registry.json", registry)
    before = events_model.read_events(page_dir)

    result = CliRunner().invoke(
        cli_model.cli,
        ["edit", str(page_dir), "--to", message["id"], "--text", "Revised."],
    )

    assert result.exit_code != 0
    assert "current layer writes" in result.output
    assert "edit" in result.output
    assert events_model.read_events(page_dir) == before


def test_markup_enters_only_through_the_cli_gate(server, page_dir):
    """The browser door refuses the field rather than silently dropping it: everything
    the log holds under `markup` has been through `check_markup`, which is what lets
    the thread structure and the panel index it unasked."""
    publish(page_dir, version=1)
    before = events_model.read_events(page_dir)
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "version": 1,
                "text": "hi",
                "markup": '<lf-diagram id="m"><pre>graph LR\n  A --> B</pre></lf-diagram>',
            }
        ).encode(),
    )
    assert status == 400
    assert "markup" in json.loads(body)["error"]
    assert events_model.read_events(page_dir) == before


def test_export_prints_threads_and_versions(page_dir):
    # The heading is the page's title as a reader sees it, entities and all.
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<title>t</title>", "<title>Cutoff &amp; backfill</title>")
    )
    CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "first cut"],
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"quote": "flip reads"},
            "text": "why?",
        },
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "id": "r1",
            "author": "claude",
            "agent": "Claude",
            "parent": "c1",
            "text": "reversibility",
            "markup": '<lf-diagram id="why"><pre>graph LR\n  A --> B</pre></lf-diagram>',
        },
    )
    events_model.append_event(
        page_dir, {"kind": "resolve", "id": "x1", "author": "user", "parent": "r1"}
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c2",
            "author": "user",
            "anchor": {"section": "flow"},
            "text": "arrow?",
        },
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "b",
            "action": "move",
            "detail": {"card": "card-x", "to": "col-done", "index": 0},
        },
    )
    # An anchor holds the whole passage, because that is the extent the page marks; a
    # transcript is prose someone pastes into an MR, so a passage of any length is
    # named by its ends and the exchange stays readable under it.
    said = "The batch replays from the top."
    long_quote = " ".join([said] * 20)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c3",
            "author": "user",
            "anchor": {"quote": long_quote},
            "text": "all of it",
        },
    )
    # An abandoned newer draft is not the live page whose exchange is exported.
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace("<title>t</title>", "<title>Abandoned draft</title>")
    )
    result = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("## Leaf: Cutoff & backfill\n")
    assert "- v1: first cut" in result.output
    # The user's direct edits are outcomes of the exchange, not just events.
    assert "### Edits" in result.output
    assert "- `b`: move card=card-x to=col-done index=0 (on v1)" in result.output

    # And one they took back is an outcome under its own name: left out it would
    # read as never made, and shown plainly it would read as final.
    moved = next(e for e in events_model.read_events(page_dir) if e["kind"] == "action")
    events_model.append_event(
        page_dir, {"kind": "undo", "author": "user", "undoes": moved["id"]}
    )
    result = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert (
        "- `b`: move card=card-x to=col-done index=0 (on v1) — taken back"
        in result.output
    )
    assert "> “flip reads”  — resolved" in result.output
    assert "- **User**: why?" in result.output
    # The widget rides its message into the transcript, indented under the words.
    assert "- **Claude**: reversibility\n  <lf-diagram" in result.output
    assert "> § flow" in result.output  # element-anchored comments keep their target
    assert long_quote not in result.output, "the whole passage went into the transcript"
    head = next(
        ln for ln in result.output.splitlines() if ln.startswith("> “The batch")
    )
    assert head.startswith(f"> “{said}") and head.endswith(f"{said}”"), head
    assert "…" in head and len(head) < len(long_quote) / 2, head


def test_markup_needs_the_registry_and_text_does_not(page_dir):
    """Text renders with every raw tag escaped, so a plain reply has nothing to
    validate and posts without the registry; markup is checked against it, so without
    one the gate refuses rather than guessing."""
    (page_dir / "registry.json").unlink()
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    plain = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "plain answer, x < y",
        ],
    )
    assert plain.exit_code == 0, plain.output
    with_markup = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "See:",
            "--markup",
            '<lf-diagram id="f"><pre>graph LR\n  A --> B</pre></lf-diagram>',
        ],
    )
    assert with_markup.exit_code != 0
    assert "no registry.json" in with_markup.output


def test_comment_requires_the_registry_its_runtime_reads(page_dir):
    published(page_dir)
    (page_dir / "registry.json").unlink()
    before = events_model.read_events(page_dir)
    result = comment(page_dir, "--quote", "Ship dark", "--text", "Still posts")
    assert result.exit_code != 0
    assert (
        "no registry.json" in result.output and "run `leaf page init`" in result.output
    )
    assert events_model.read_events(page_dir) == before


def test_note_refuses_a_version_that_fails_check(page_dir):
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace("</section>", ""))
    result = CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "broken"],
    )
    assert result.exit_code != 0
    assert "refusing to publish" in result.output
    assert live_versions(page_dir) == []


def test_example_layer_names_repository_packages():
    examples = ROOT / "examples"
    packages = json.loads((examples / "layer.json").read_text(encoding="utf-8"))

    assert packages
    assert all(not Path(name).is_absolute() for name in packages)
    assert all((ROOT / name).is_dir() for name in packages)
    assert layer_model.checked_inputs([ROOT / name for name in packages])


def test_every_seeded_fragment_passes_the_door_it_never_came_through(
    tmp_path, monkeypatch
):
    """A hand-written seed is the one markup in the product no gate has read.

    Markup reaches a page two ways. A version goes through `version check`. An
    event's `markup` goes through `leaf reply`, which validates it and then freezes
    it in an append-only log, so that door is the last moment anything about it can
    be fixed. An example's companion log is neither: it is written into the
    repository by hand, and from there `scripts/site.py` publishes it to
    leaf.page, `serve` lays it into every browser sweep, and `scripts/preview.py`
    hands it to a reader. `version check` reads such a log only for ids colliding
    with the version's.

    So the seed is put through the real door rather than through a list of checks
    copied out of it — that door is where a check lands, and a second gate spelling
    out today's list is the one that goes on not asking whatever the first learns
    to. `/media/nope.png` in a seeded `lf-shot` is the shape of what it would catch:
    refused in a version, and until recently accepted in a reply. No seed carries one
    today, which is what a floor is for."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    seeded = [
        p
        for p in sorted((ROOT / "examples").glob("*.html"))
        if p.with_suffix(".jsonl").exists()
    ]
    assert seeded, "no example ships a log; this gate is reading nothing"
    packages = json.loads((ROOT / "examples" / "layer.json").read_text())
    link_command_hub_package(tmp_path)
    selection_args = [arg for package in packages for arg in ("--package", package)]
    read = 0
    for example in seeded:
        d = tmp_path / f"door-{example.stem}"
        initialized = CliRunner().invoke(
            cli_model.cli, ["page", "init", *selection_args, str(d)]
        )
        assert initialized.exit_code == 0, f"{example.name}: {initialized.output}"
        (d / "versions" / "v1.html").write_text(example.read_text())
        shutil.copytree(ROOT / "examples" / "media", d / "media", dirs_exist_ok=True)
        # Published, because the door is only open on a page a reader could be
        # holding — which is the state every one of these seeds is written for.
        published = CliRunner().invoke(
            cli_model.cli,
            [
                "version",
                "publish",
                str(d),
                "--version",
                "1",
                "--text",
                "the page as it ships",
            ],
        )
        assert published.exit_code == 0, f"{example.name}: {published.output}"
        opened = CliRunner().invoke(
            cli_model.cli, ["comment", str(d), "--text", "what a reader would ask"]
        )
        assert opened.exit_code == 0, opened.output
        root = json.loads(opened.output)["id"]
        # The writer's own separator, never splitlines(): its wider class reads a
        # U+2028 inside a message's text as a break.
        for line in (
            example.with_suffix(".jsonl").read_text(encoding="utf-8").split("\n")
        ):
            if not line.strip() or not (markup := json.loads(line).get("markup")):
                continue
            read += 1
            posted = CliRunner().invoke(
                cli_model.cli,
                [
                    "reply",
                    str(d),
                    "--to",
                    root,
                    "--text",
                    "carrying it",
                    "--markup",
                    markup,
                ],
            )
            assert posted.exit_code == 0, (
                f"{example.name} seeds markup the reply door would refuse:\n"
                f"{posted.output}"
            )
    assert read, (
        "no seeded event carries markup, so this read nothing — see "
        "examples/CLAUDE.md on what a log is for"
    )
