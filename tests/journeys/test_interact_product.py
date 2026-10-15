"""Version corpus, registry, message, and export tests."""

import leaf.validation.command as checking_command
import pytest
from interact_support import (
    PAGE,
    ROOT,
    check,
    found,
    fragment_errors,
    publish,
)
from leaf.registry import storage as registry_storage
from leaf_dev.page_fixtures import prepare_page, read_fixture
from model.test_interact_product import PAGE_FIXTURES, run_leaf


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
    assert checking_command.cmd_check(page_dir) == 0

    (page_dir / "index.html").write_text(PAGE)
    assert checking_command.cmd_check(page_dir) == 0


# One case per fixture, named by its path since notes each keep a `playground.html`, so
# every fixture that fails is reported rather than only the first, and the cases spread
# across workers rather than holding one for the whole tree.
@pytest.mark.parametrize(
    "example",
    PAGE_FIXTURES,
    ids=[
        example.relative_to(ROOT).with_suffix("").as_posix()
        for example in PAGE_FIXTURES
    ],
)
def test_page_fixtures_pass_check(example, tmp_path, monkeypatch, initialized_page):
    """Every page fixture in the tree passes the real check: each public example and
    developer feature fixture, and each playground a note previews. A note's page
    is built by nothing else before a user asks for it, so without this a
    playground that names media it never committed stays green until preview
    refuses it."""
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
