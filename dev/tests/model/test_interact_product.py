"""Developer tooling checks; run explicitly from dev/tests."""

import json

from leaf.structure import SourceDocument
from leaf_dev import ROOT


def test_corpus_is_generated_from_the_examples():
    """examples/corpus.html is derived; a commit that lets it drift fails here."""
    from leaf_dev.commands import corpus

    committed = (ROOT / "examples" / "corpus.html").read_text()
    assert corpus.build() == committed, "examples changed — rerun leaf-dev corpus"

    # Composition keeps each source's outline, including the ones inside live
    # samples: the corpus tab and sample document provide their existing scopes.
    def contents(document):
        return {
            node["attrs"]["id"]
            for node in document.lf_elements
            if node["tag"] == "lf-toc"
        }.union(*(contents(sample["document"]) for sample in document.samples))

    expected = set().union(
        *(contents(SourceDocument(source.read_text())) for source in corpus.SOURCES)
    )
    assert expected
    assert contents(SourceDocument(committed)) == expected
    committed_data = json.loads((ROOT / "examples" / "corpus.data.json").read_text())
    assert corpus.build_data() == committed_data, (
        "example data changed — rerun leaf-dev corpus"
    )
    assert corpus.build_events() == corpus.CORPUS_EVENTS.read_text(), (
        "sample threads changed — rerun leaf-dev corpus"
    )
    committed_page = {
        path.relative_to(corpus.CORPUS_PAGE).as_posix(): path.read_bytes()
        for path in corpus.CORPUS_PAGE.rglob("*")
        if path.is_file()
    }
    assert corpus.build_page() == committed_page, (
        "an example's own elements changed — rerun leaf-dev corpus"
    )
    assert committed_data["$captures"]["gallery-source"]["file"] == (
        "developer/feature-gallery-source.toml"
    )
