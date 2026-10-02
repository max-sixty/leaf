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
        # the activity feed's rows are the log's history, and a text document's lines
        # are its bound source's value, wrapped at the column's width.
        ("lf-activity", "keeps-first-box"),
        ("lf-text-document", "keeps-first-box"),
        # Which form the contents takes, the fixed map in the margin or the outline in
        # the flow, is the margin pass's residency decision (`data-lf-margin`,
        # margin-layout.js), made from the room it measures after the first paint.
        ("lf-toc", "keeps-first-box"),
    },
    # The widgets below generate an interface of wrapped words, whose height follows the
    # viewer's fonts: each example drew 22px to 45px taller on CI's Linux than on
    # macOS. No height a page states holds on every platform, so their examples state
    # none. Where one declares x-height, a page's data-height is an estimate taken on
    # the author's machine, which `page check --render` advises.
    "gallery": {("lf-margin-entry-gallery", "keeps-first-box")},
    # The module builds each control's inputs and the instruction's current values,
    # which it restores per viewer from the tab's storage, so neither the rail's
    # members nor the words the instruction wraps exist before it runs. With a stated
    # height the stage stands in its region from first paint.
    "playground": {
        ("lf-playground", "keeps-first-box"),
        ("lf-playground-control", "keeps-first-box"),
        ("lf-playground-output", "keeps-first-box"),
        ("lf-playground-preview", "keeps-first-box"),
        ("lf-playground-value", "keeps-first-box"),
    },
    "targeting": {("lf-targeting", "keeps-first-box")},
}
