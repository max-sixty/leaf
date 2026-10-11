"""The widget quality findings Leaf's own widgets still have, each a defect waiting on
its fix (`leaf/render_gate/widget_quality.py`, `test_widget_quality.py`).

`KNOWN` names each finding by package directory, tag, and check. A finding it does not
name fails the test, and so does an entry that no longer occurs: fixing a widget
deletes its entry, so the list only shrinks. A widget joins only as a defect to fix,
never as behavior to keep. The corpus sweep reads the same list, since a defect is the
widget's wherever it stands (`test_render_gate.py`, `held_scroller_findings`)."""

from interact_support import SKILL_ROOT
from leaf import schema as schema_model

# The base layer's two halves and every bundled package, each answering for its own
# widgets as a package author's `package check --render` would.
PACKAGES = [
    schema_model.ASSETS,
    *sorted(path for path in (SKILL_ROOT / "packages").iterdir() if path.is_dir()),
]

KNOWN = {
    "default": {
        # What these draw is the page's state, which arrives with the first state
        # answer after the first paint and which the served document does not carry:
        # a text document's lines are its bound source's value, wrapped at the column's width.
        ("lf-text-document", "keeps-first-box"),
        # The contents are written empty and build their list from the page's
        # headings as the module upgrades, so the first paint has no box to keep.
        # Residency (`data-lf-margin`, prepaint.js) already decides their form
        # before that paint.
        ("lf-toc", "keeps-first-box"),
    },
    "file-editor": {
        # The problem panel caps itself at `min(50%, 20rem)` in an auto grid row, where
        # the percentage resolves against the panel's own content, so a two-line problem
        # is cut to 78px and scrolls inside it. Capping it from
        # `--lf-file-editor-height` instead shows the problem whole, but its height then
        # follows the problem's text, and test_render_files.py's in-flight save journey
        # reads a 17px shift without input in the editor's shadow tree.
        ("lf-file-editor", "grows-with-content"),
    },
}
