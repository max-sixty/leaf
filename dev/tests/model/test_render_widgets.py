"""Board, suggestion, ask, and widget composition tests."""

from leaf_dev.commands import corpus as corpus_model

from leaf.structure import SourceDocument


def test_the_composed_corpus_carries_each_examples_head_modules():
    """A playground whose head module draws its samples, as the notification
    playground's does, runs inside the composed corpus because the corpus hoists every
    example's early head script into its own head (`leaf_dev.commands.corpus`). Each example's
    own page test runs the module; this holds the composition to carrying it."""
    composed = {
        script["body"]
        for script in SourceDocument(
            corpus_model.build(corpus_model.sources())
        ).authoring.inline_scripts
        if script["early_head"]
    }
    carried = 0
    for source in corpus_model.sources():
        for script in SourceDocument(source.read_text()).authoring.inline_scripts:
            if script["early_head"]:
                assert script["body"] in composed, source.name
                carried += 1
    assert carried, "no example has a head script, so nothing was checked"


def test_the_composed_corpus_preserves_stylesheet_access():
    """Each source stylesheet keeps its declarations when the corpus hoists it."""
    composed = SourceDocument(
        corpus_model.build(corpus_model.sources())
    ).authoring.style_blocks
    for source in corpus_model.sources():
        for sheet in SourceDocument(source.read_text()).authoring.style_blocks:
            assert any(
                item["css"].strip() == sheet["css"].strip()
                and item["attrs"] == sheet["attrs"]
                for item in composed
            ), source.name
