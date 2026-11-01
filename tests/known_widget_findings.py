"""Observed widget-quality limits, including accepted content-derived startup changes
(`leaf/render_gate/widget_quality.py`, `test_widget_quality.py`).

`KNOWN` names each finding by package directory, tag, and check. A finding it does not
name fails the test, and so does an entry that no longer occurs. Each entry names an
observed limitation or an explicitly accepted content-derived startup change, with its
reason beside it. The corpus sweep reads the same list, since a widget's defect is
its own wherever it stands (`test_render_gate.py`, `held_scroller_findings`)."""

from leaf import schema as schema_model

# The base layer's two halves and every bundled package, each answering for its own
# widgets as a package author's `package check --render` would.
PACKAGES = [
    schema_model.ASSETS,
    *sorted(
        path for path in (schema_model.BUNDLED_PACKAGES).iterdir() if path.is_dir()
    ),
]

KNOWN: dict[str, set[tuple[str, str]]] = {
    # The screenshot's fitted canvas reads decoded image dimensions, available
    # space and crop. Reserving only its toolbar would leave the image-height jump.
    "default": {("lf-shot", "keeps-first-box")},
    # Formatting replaces raw unified-diff header lines with file/hunk rows.
    # Matching that content-derived height before upgrade needs another renderer.
    "diff": {("lf-diff", "keeps-first-box")},
    # The authored event list becomes a chart whose labels are packed from measured
    # text. Duplicating that layout in CSS would restore a second renderer.
    "timeline": {("lf-timeline", "keeps-first-box")},
}
