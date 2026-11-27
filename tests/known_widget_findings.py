"""Observed widget-quality limits, including accepted content-derived startup changes
(`leaf/pages/render_gate/widget_quality.py`, `test_widget_quality.py`).

`KNOWN` names each finding by package directory, tag, and check. A finding it does not
name fails the test, and so does an entry that no longer occurs. Each entry names an
observed limitation or an explicitly accepted content-derived startup change, with its
reason beside it. The corpus sweep reads the same list, since a widget's defect is
its own wherever it stands (`test_render_gate.py`, `held_scroller_findings`)."""

from leaf.base import schema as schema_model

# The base layer's two halves and every bundled package, each answering for its own
# widgets as a package author's `package check --render` would.
PACKAGES = [
    schema_model.ASSETS,
    *sorted(
        path for path in (schema_model.BUNDLED_PACKAGES).iterdir() if path.is_dir()
    ),
]

KNOWN: dict[str, set[tuple[str, str]]] = {
    # An age first paints the time its author wrote, which the runtime replaces with
    # the age itself, whose width changes as it grows; its registry entry tells the
    # author to end the line with it or reserve its room.
    "browser": {("lf-age", "keeps-first-box")},
    # A written Markdown preview first paints its source, which the module replaces
    # with the rendering. Matching the rendering's height before upgrade needs the
    # Markdown renderer.
    "default": {("lf-text-document", "keeps-first-box")},
    # Formatting replaces raw unified-diff header lines with file/hunk rows.
    # Matching that content-derived height before upgrade needs another renderer.
    "diff": {("lf-diff", "keeps-first-box")},
    # The live view sets the preview beside the aside and draws the presets'
    # buttons and the bar of actions, so the playground resizes once on activation.
    "playground": {
        ("lf-playground", "keeps-first-box"),
        ("lf-playground-preset", "keeps-first-box"),
    },
    # The authored event list becomes a chart whose labels are packed from measured
    # text. Duplicating that layout in CSS would restore a second renderer.
    "timeline": {("lf-timeline", "keeps-first-box")},
}
