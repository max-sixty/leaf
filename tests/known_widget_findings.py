"""The widget quality findings Leaf's own widgets still have, each a defect waiting on
its fix (`leaf/render_gate/widget_quality.py`, `test_widget_quality.py`).

`KNOWN` names each finding by package directory, tag, and check. A finding it does not
name fails the test, and so does an entry that no longer occurs: fixing a widget
deletes its entry, so the list only shrinks. A widget joins only as a defect to fix,
never as behavior to keep. The corpus sweep reads the same list, since a defect is the
widget's wherever it stands (`test_render_gate.py`, `held_scroller_findings`)."""

from leaf import schema as schema_model

# The base layer's two halves and every bundled package, each answering for its own
# widgets as a package author's `package check --render` would.
PACKAGES = [
    schema_model.ASSETS,
    *sorted(
        path for path in (schema_model.BUNDLED_PACKAGES).iterdir() if path.is_dir()
    ),
]

KNOWN: dict[str, set[tuple[str, str]]] = {}
