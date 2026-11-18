"""Developer tooling checks; run explicitly from dev/tests."""

import html
import subprocess
from typing import cast

import pytest

from leaf.structure import SourceDocument
from leaf_dev import docs
from leaf_dev.commands.site import demo as record_demo
from leaf_dev.example_data import catalog_sources, document_metadata, named_source


def test_catalog_cards_name_the_packages_their_example_uses(tmp_path, monkeypatch):
    """A card names each bundled package whose element its example's markup uses."""
    source = named_source("examples")
    for example in catalog_sources():
        (tmp_path / example.name).write_text(example.read_text())
    (tmp_path / "review-a-plan.html").write_text(
        "<!doctype html><title>Plan</title><meta name=description content=Plan>"
        '<main><lf-diff id="d"></lf-diff><lf-timeline id="t"></lf-timeline></main>'
    )
    monkeypatch.setattr(docs, "EXAMPLES", tmp_path)
    composed = SourceDocument(docs.compose(source, source.read_text())).tree
    card = composed.select_one(
        'a.example-link[href="/examples/review-a-plan/"] .example-packages'
    )
    assert card is not None
    assert card.text == "diff · timeline"


def test_catalog_descriptions_follow_example_metadata(tmp_path, monkeypatch):
    """A page edit changes its catalog caption without editing the catalog.

    The catalog authors its selection, grouping and order; every builder composes
    each caption from its example's description, escaped as text.
    """
    source = named_source("examples")
    catalog = source.read_text()
    links = SourceDocument(catalog).tree.select("a.example-link")
    for example in catalog_sources():
        (tmp_path / example.name).write_text(example.read_text())
    changed = tmp_path / "review-a-plan.html"
    _, old = document_metadata(changed)
    description = 'Review a plan & choose <the next step> with "clear evidence".'
    changed.write_text(
        changed.read_text().replace(
            html.escape(old, quote=True), html.escape(description, quote=True)
        )
    )
    monkeypatch.setattr(docs, "EXAMPLES", tmp_path)
    composed = SourceDocument(docs.compose(source, catalog)).tree
    assert [link.attrs["href"] for link in composed.select("a.example-link")] == [
        link.attrs["href"] for link in links
    ]
    for link in composed.select("a.example-link"):
        _, expected = document_metadata(tmp_path / f"{docs.example_name(link)}.html")
        select_one_result = link.select_one(".example-description")
        assert select_one_result is not None
        assert select_one_result.text == expected
    select_one_result_2 = composed.select_one(
        'a[href="/examples/review-a-plan/"] .example-description'
    )
    assert select_one_result_2 is not None
    assert select_one_result_2.text == description


@pytest.mark.parametrize(
    ("slot", "copy"),
    [
        (
            '<nav class="sitenav" aria-label="Site"></nav>',
            '<nav class="sitenav" aria-label="Site"><a href="/">leaf</a></nav>',
        ),
        (
            '<img\n                alt="Sandbox',
            '<img src="/media/0000000000000000.jpg"\n                alt="Sandbox',
        ),
    ],
)
def test_a_composed_part_refuses_an_authored_copy(slot, copy):
    """A slot holding a copy of its owner's facts would go stale silently."""
    source = named_source("index")
    authored = source.read_text()
    assert slot in authored
    with pytest.raises(ValueError, match="composed from its owner"):
        docs.compose(source, authored.replace(slot, copy))


def test_demo_waiter_preserves_the_reason_a_wait_delivered_nothing():
    class FailedWait:
        returncode = 2

        def communicate(self, *, timeout):
            assert timeout == 10
            return "", "the page closed while waiting\n"

    waiter = object.__new__(record_demo.DemoWaiter)
    # The waiter only observes communicate and returncode in this failure path.
    waiter.process = cast(subprocess.Popen[str], FailedWait())

    with pytest.raises(
        RuntimeError,
        match="the demo waiter exited 2 without one batch of user events\\n"
        "the page closed while waiting",
    ):
        waiter.receive()
