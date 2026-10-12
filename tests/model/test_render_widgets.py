"""Board, suggestion, ask, and widget composition tests."""

from leaf.structure import SourceDocument
from leaf_dev import corpus as corpus_model


def test_the_composed_corpus_carries_each_examples_head_modules():
    """A playground whose head module draws its samples, as the notification
    playground's does, runs inside the composed corpus because the corpus hoists every
    example's early head script into its own head (`leaf_dev.corpus`). Each example's
    own page test runs the module; this holds the composition to carrying it."""
    composed = {
        script["body"]
        for script in SourceDocument(corpus_model.CORPUS.read_text()).inline_scripts
        if script["early_head"]
    }
    carried = 0
    for source, _ in corpus_model.TABS:
        for script in SourceDocument(source.read_text()).inline_scripts:
            if script["early_head"]:
                assert script["body"] in composed, source.name
                carried += 1
    assert carried, "no example has a head script, so nothing was checked"
