"""Observed widget-quality limits (`leaf/render_gate/widget_quality.py`,
`test_widget_quality.py`).

`KNOWN` names each finding by package directory, tag, and check. A finding it does not
name fails the test, and so does an entry that no longer occurs. Each entry names an
observed limitation, with its reason beside it. The corpus sweep reads the same list,
since a widget's defect is its own wherever it stands (`test_render_gate.py`,
`held_scroller_findings`)."""

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
