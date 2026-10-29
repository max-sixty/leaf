"""Developer tooling checks; run explicitly from dev/tests."""

import json

from leaf.structure import SourceDocument
from leaf_dev.commands import corpus
from leaf_dev.example_data import data_file, named_source, page_files, seed_log


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


def test_corpus_rebuilds_sources_and_removes_retired_page_files(tmp_path, monkeypatch):
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
    monkeypatch.setattr(corpus, "DEVELOPER_SOURCES", ())
    output = named_source("corpus", root=tmp_path)
    assert "Before" in output.read_text()
    assert (page_files(output) / "sample.js").is_file()
    source.write_text(source.read_text().replace("Before", "After"))
    (files / "sample.js").unlink()
    assert named_source("corpus", root=tmp_path) == output
    assert "After" in output.read_text()
    assert not (page_files(output) / "sample.js").exists()
