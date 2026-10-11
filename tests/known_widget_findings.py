"""The widget quality findings Leaf's own widgets still have, each a defect waiting on
its fix (`leaf/render_gate/widget_quality.py`, `test_widget_quality.py`).

`KNOWN` names each finding by package directory, tag, and check. A finding it does not
name fails the test, and so does an entry that no longer occurs: fixing a widget
deletes its entry, so the list only shrinks. A widget joins only as a defect to fix,
never as behavior to keep."""

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
}
