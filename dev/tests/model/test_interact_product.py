"""Developer tooling checks; run explicitly from dev/tests."""

import json

import pytest

from leaf.structure import SourceDocument
from leaf_dev.commands.generate import corpus as corpus
from leaf_dev.example_data import (
    CORPUS,
    authored_sources,
    data_file,
    named_source,
    page_files,
    published_sources,
    seed_log,
)


def test_corpus_is_generated_from_the_examples():
    """A named corpus builds its markup, data, history and custom widgets."""
    source = named_source("corpus")

    # Composition keeps each source's outline, including the ones inside live
    # samples: the corpus tab and sample document provide their existing scopes.
    def contents(document):
        return {
            node["attrs"]["id"]
            for node in document.lf_elements
            if node["tag"] == "lf-toc"
        }.union(*(contents(sample["document"]) for sample in document.samples))

    expected = set().union(
        *(contents(SourceDocument(path.read_text())) for path in corpus.sources())
    )
    assert expected
    assert contents(SourceDocument(source.read_text())) == expected
    data = json.loads(data_file(source).read_text())
    capture = data["$captures"]["gallery-source"]["file"]
    assert (source.parent / capture).is_file()
    assert seed_log(source).read_text()
    registry = json.loads((page_files(source) / "registry.json").read_text())
    assert "lf-conversation-workspace" in registry
    assert (page_files(source) / "widgets/lf-conversation-workspace.js").is_file()
    # Each instance keeps the same payload contract on its own and in the corpus.
    for example in corpus.sources():
        declaration = page_files(example) / "registry.json"
        if declaration.is_file():
            contracts = (
                json.loads(declaration.read_text())
                .get("$data", {})
                .get("contracts", {})
            )
            for name, contract in contracts.items():
                assert registry["$data"]["contracts"][name] == contract
    # Repeated requests leave an unchanged snapshot alone, including its preview watcher.
    modified = source.stat().st_mtime_ns
    assert named_source("corpus") == source
    assert source.stat().st_mtime_ns == modified


def test_corpus_rebuilds_sources_and_removes_retired_page_files(tmp_path):
    """Regeneration follows authored edits and drops a removed custom widget."""
    examples = tmp_path / "examples"
    examples.mkdir()
    source = examples / "sample.html"
    source.write_text(
        "<html><head><title>Sample</title></head><body><main><p>Before</p></main></body></html>"
    )
    files = page_files(source)
    files.mkdir()
    (files / "sample.js").write_text("// sample\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "examples.html").write_text(
        '<a class="example-link" href="/examples/sample/">Sample</a>'
    )
    output = named_source("corpus", root=tmp_path)
    assert "Before" in output.read_text()
    assert (page_files(output) / "sample.js").is_file()
    source.write_text(source.read_text().replace("Before", "After"))
    (files / "sample.js").unlink()
    assert named_source("corpus", root=tmp_path) == output
    assert "After" in output.read_text()
    assert not (page_files(output) / "sample.js").exists()


def test_only_the_generated_corpus_is_not_an_authored_page(tmp_path):
    """Every reader takes its pages from `example_data`, so a worked example named
    like the corpus is composed, published and picked by name as any other is."""
    pages = {
        "notes": tmp_path / "examples" / "corpus-notes.html",
        "gallery": tmp_path / "examples" / "developer" / "gallery.html",
        "fixture": tmp_path / "tests" / "fixtures" / "pages" / "fixture.html",
    }
    for name, page in pages.items():
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            f"<html><head><title>{name}</title></head>"
            f'<body><main><p id="{name}">{name}</p></main></body></html>'
        )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "examples.html").write_text("")

    generated = named_source("corpus", root=tmp_path)
    assert generated == tmp_path / CORPUS
    assert corpus.source_root(generated) == tmp_path
    assert 'id="corpus-corpus-notes"' in generated.read_text()
    assert authored_sources(tmp_path) == list(pages.values())
    assert published_sources(tmp_path) == [pages["notes"], pages["gallery"]]
    assert named_source("corpus-notes", root=tmp_path) == pages["notes"]
    assert corpus.source_root(pages["notes"]) is None

    # A page that shares the corpus's name is authored, so the name picks two sources.
    shadow = tmp_path / "examples" / "developer" / "corpus.html"
    shadow.write_text(pages["gallery"].read_text().replace("gallery", "shadow"))
    assert shadow in published_sources(tmp_path)
    with pytest.raises(ValueError, match="corpus names more than one source"):
        named_source("corpus", root=tmp_path)
