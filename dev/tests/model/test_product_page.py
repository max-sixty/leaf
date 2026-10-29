"""Developer tooling checks; run explicitly from dev/tests."""

import html
import subprocess
from typing import cast

import pytest
from model.test_product_page import DOCS, EXAMPLES

from leaf.structure import SourceDocument
from leaf_dev import declared_records, docs
from leaf_dev.commands import record_demo
from leaf_dev.example_data import document_metadata


def test_catalog_descriptions_follow_example_metadata(tmp_path, monkeypatch):
    """A page edit changes its catalog caption without editing the catalog.

    The catalog authors its selection, grouping and order; every builder composes
    each caption from its example's description, escaped as text.
    """
    source = DOCS / "examples.html"
    catalog = source.read_text()
    links = SourceDocument(catalog).tree.select("a.example-link")
    for link in links:
        name = docs.example_name(link)
        (tmp_path / f"{name}.html").write_text((EXAMPLES / f"{name}.html").read_text())
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
    source = DOCS / "index.html"
    authored = source.read_text()
    assert slot in authored
    with pytest.raises(ValueError, match="composed from its owner"):
        docs.compose(source, authored.replace(slot, copy))


def test_data_structures_page_lists_every_declared_schema():
    """Each served definition, event kind and record gets an entry, and every link
    between entries lands on one."""
    source = DOCS / "data-structures.html"
    tree = SourceDocument(docs.compose(source, source.read_text())).tree
    entries = {entry.attrs["id"] for entry in tree.select("section.schema-entry")}
    registry = docs.read_json(docs.KERNEL_REGISTRY)["$events"]
    expected = {
        "served-state",
        "event-envelope",
        "interaction-batch",
        "record-draft",
        *(f"served-{name}" for name in docs.read_json(docs.SERVED_SCHEMA)["$defs"]),
        *(f"event-{kind}" for kind in registry["kinds"]),
        *(f"record-{kind}" for kind in declared_records()),
    }
    assert entries == expected
    targets = set()
    for link in tree.select('a[href^="#"]'):
        href = link.attrs["href"]
        assert isinstance(href, str)
        targets.add(href[1:])
    assert targets - entries <= {"events"}


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
