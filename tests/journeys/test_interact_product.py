"""Version corpus, registry, message, and export tests."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    ROOT,
    check,
    comment,
    found,
    fragment_errors,
    publish,
)
from leaf_dev.example_data import named_source
from leaf_dev.page_fixtures import prepare_page, read_fixture
from model.test_interact_product import CORPUS_SOURCES, PAGE_FIXTURES, run_leaf

import leaf.validation.command as checking_command
from leaf import cli as cli_model
from leaf.registry import storage as registry_storage


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
        run_leaf,
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
    its markup. From there `leaf-dev site` publishes it to
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
    seeded = [p for p in CORPUS_SOURCES if p.with_suffix(".jsonl").exists()]
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
            d, read_fixture(example), run_leaf, seed_log=False, final_status=None
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
