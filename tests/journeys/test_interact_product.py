"""Version corpus, registry, message, and export tests."""

import json

import click
import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    ROOT,
    append_carried_log_record,
    check,
    comment,
    found,
    fragment_errors,
    page_packages,
    publish,
    response_reference,
)
from model.test_interact_product import PAGE_FIXTURES

import leaf.validation.command as checking_command
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.registry import storage as registry_storage
from leaf_dev.example_data import authored_sources, named_source
from leaf_dev.page_fixtures import leaf_in_process, prepare_page, read_fixture


def test_a_settled_group_keeps_an_id_but_an_unreferenced_group_may_leave(page_dir):
    """A settled group needs an id for its disclosure state, but the whole
    unreferenced group may leave a later revision."""
    registry = registry_storage.load_registry(page_dir)
    assert found(
        fragment_errors(
            '<lf-options settled><lf-option id="o1"><strong>A</strong></lf-option></lf-options>',
            registry,
        ),
        "attribute-schema",
        keyword="dependentRequired",
    )

    group = (
        '<lf-ask id="pick-decision"><h2>Which one?</h2><lf-options id="pick" choose{}>'
    )
    group += '<lf-option id="opt-a"{}><strong>A</strong></lf-option>'
    group += (
        '<lf-option id="opt-b"><strong>B</strong></lf-option></lf-options></lf-ask>'
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("</main>", group.format("", "") + "</main>")
    )
    publish(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace("</main>", group.format(" settled", " chosen") + "</main>")
    )
    assert checking_command.cmd_check(page_dir)["status"] == 0

    (page_dir / "index.html").write_text(PAGE)
    assert checking_command.cmd_check(page_dir)["status"] == 0


# One case per fixture, named by its path since notes each keep a `playground.html`, so
# every fixture that fails is reported rather than only the first, and the cases spread
# across workers rather than holding one for the whole tree.
@pytest.mark.parametrize(
    "example",
    (*PAGE_FIXTURES, "corpus"),
    ids=[
        example.relative_to(ROOT).with_suffix("").as_posix()
        for example in PAGE_FIXTURES
    ]
    + ["corpus"],
)
def test_page_fixtures_pass_check(example, tmp_path, monkeypatch, initialized_page):
    """Every page fixture in the tree passes the real check: each public example and
    developer feature fixture, and each playground a note previews. A note's page
    is built by nothing else before a user asks for it, so without this a
    playground that names media it never committed stays green until preview
    refuses it."""
    if example == "corpus":
        example = named_source("corpus")
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    fixture = read_fixture(example)
    d = initialized_page(tmp_path / "page", fixture.packages)

    def checked(version):
        result = check(d)
        assert result.exit_code == 0, f"{version.name}: {result.output}"

    # Every authored version, not only the current one: a fault in a prior
    # version stops preview and the site build, a slow way to hear it.
    prepare_page(
        d,
        fixture,
        leaf_in_process,
        initialize=False,
        final_status=None,
        each_version=checked,
    )


def test_every_seeded_fragment_passes_the_door_it_never_came_through(
    tmp_path, monkeypatch
):
    """A hand-written seed is the one markup in the product no gate has read.

    Markup reaches a page two ways. A version goes through `page check`. An
    event's `markup` goes through `leaf thread reply`, which validates it and then freezes
    it in an append-only log, so that door is the last moment anything about it can
    be fixed. An example's companion log is neither: it is written into the
    repository by hand, and the append door it goes through reads the event, not
    its markup. From there `leaf-dev site build` publishes it to
    leaf.page, `serve` lays it into every browser sweep, and `leaf-dev preview`
    serves it live. `page check` reads such a log only for ids colliding
    with the version's.

    So the seed is put through the real door rather than through a list of checks
    copied out of it — that door is where a check lands, and a second gate spelling
    out today's list is the one that goes on not asking whatever the first learns
    to. `/media/nope.png` in a seeded `lf-shot` is the shape of what it would catch:
    refused in a version, and until recently accepted in a reply. No seed carries one
    today, which is what a floor is for."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    seeded = [p for p in authored_sources() if p.with_suffix(".jsonl").exists()]
    assert seeded, "no example ships a log; this gate is reading nothing"
    read = 0
    for example in seeded:
        # Only messages carrying markup or obligations exercise this door. Plain
        # threads are covered by the complete fixture check.
        # Use the log writer's separator: splitlines() also splits message U+2028.
        fragments = [
            event
            for line in example.with_suffix(".jsonl").read_text().split("\n")
            if line.strip()
            and ((event := json.loads(line)).get("markup") or event.get("obligation"))
        ]
        if not fragments:
            continue
        d = tmp_path / f"door-{example.stem}"
        # Published, because the door is only open on a page a user could be
        # holding — which is the state every one of these seeds is written for.
        # The seed itself stays out: its fragments go through the door below.
        prepare_page(
            d, read_fixture(example), leaf_in_process, seed_log=False, final_status=None
        )
        opened = comment(d, "--text", "what a user would ask")
        assert opened.exit_code == 0, opened.output
        root = json.loads(opened.output)["id"]
        for event in fragments:
            read += 1
            posted = CliRunner().invoke(
                cli_model.cli,
                [
                    "thread",
                    "reply",
                    str(d),
                    root,
                    "--text",
                    event["text"],
                    *(["--markup", event["markup"]] if event.get("markup") else []),
                    *(["--obligation"] if event.get("obligation") else []),
                ],
            )
            assert posted.exit_code == 0, (
                f"{example.name} seeds a message the reply door would refuse:\n"
                f"{posted.output}"
            )
    assert read, (
        "no seeded event carries markup or an obligation, so this read nothing — see "
        "examples/AGENTS.md on what a log is for"
    )


def test_reply_validates_widget_markup(page_dir):
    """The current layer checks replies; older layers do not constrain their markup."""

    def init(*packages):
        result = CliRunner().invoke(
            cli_model.cli,
            ["page", "init", str(page_dir)]
            + [arg for package in packages for arg in ("--package", package)],
        )
        assert result.exit_code == 0, result.output

    # An earlier version under a layer without `diagram`'s lf-diagram.
    init(*(package for package in page_packages() if package != "diagram"))
    publish(page_dir)
    init(*page_packages())
    publish(page_dir)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )

    def reply(markup):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, "c1"),
                "--text",
                "See:",
                "--markup",
                markup,
            ],
        )

    bad = reply('<lf-diagram id="f"><pre>graph LR</pre><b>x</b></lf-diagram>')
    assert bad.exit_code != 0
    assert "its body is one <pre> holding the text" in bad.output
    good = reply('<lf-diagram id="f"><pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>')
    assert good.exit_code == 0, good.output
    event = events_model.read_events(page_dir)[-1]
    assert event["kind"] == "reply"
    assert event["author"] == "agent"
    assert event["text"] == "See:"
    assert event["markup"].startswith("<lf-diagram")


def test_a_seed_no_writer_could_send_stops_the_page_it_seeds(tmp_path, monkeypatch):
    """An example's companion log enters through the append door, so a seed in a
    shape no real page holds fails the build that lays it in, rather than reaching
    the site and every sweep. A line copied from a stored log is that shape: it
    carries what admission derives, which goes stale as the contract moves. A
    line separator inside a message stays inside it."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    source = tmp_path / "seeded.html"
    source.write_text(PAGE)
    stored = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Why this plan?\u2028Spring is soon.",
        "anchor": {"section": "plan"},
        "attention": True,
    }
    source.with_suffix(".jsonl").write_text(
        json.dumps(stored, ensure_ascii=False) + "\n"
    )
    with pytest.raises(click.ClickException, match="attention"):
        prepare_page(
            tmp_path / "page", read_fixture(source), leaf_in_process, final_status=None
        )
    del stored["attention"]
    source.with_suffix(".jsonl").write_text(
        json.dumps(stored, ensure_ascii=False) + "\n"
    )
    page = tmp_path / "admitted"
    prepare_page(page, read_fixture(source), leaf_in_process, final_status=None)
    [seeded] = [e for e in events_model.read_events(page) if e["kind"] == "comment"]
    assert seeded["attention"] is True
    assert seeded["text"] == stored["text"]
