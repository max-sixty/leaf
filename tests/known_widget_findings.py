"""The widget quality findings Leaf's own widgets still have, each a defect waiting on
its fix (`leaf/render_gate/widget_quality.py`, `test_widget_quality.py`).

`KNOWN` names each finding by package directory, tag, and check. A finding it does not
name fails the test, and so does an entry that no longer occurs: fixing a widget
deletes its entry, so the list only shrinks. A widget joins only as a defect to fix,
never as behavior to keep."""

KNOWN = {
    "command-hub": {
        ("lf-agent", "keeps-first-box"),
        ("lf-command", "keeps-first-box"),
        ("lf-command-readings", "keeps-first-box"),
        ("lf-task", "keeps-first-box"),
        ("lf-worktree", "keeps-first-box"),
    },
    "default": {
        ("lf-activity", "keeps-first-box"),
        ("lf-chart", "keeps-first-box"),
        ("lf-code", "keeps-first-box"),
        ("lf-gloss", "keeps-first-box"),
        ("lf-milestone", "keeps-first-box"),
        ("lf-note", "keeps-first-box"),
        ("lf-option", "keeps-first-box"),
        ("lf-shot", "keeps-first-box"),
        ("lf-tab", "keeps-first-box"),
        ("lf-tabs", "keeps-first-box"),
        ("lf-text-document", "keeps-first-box"),
        ("lf-toc", "keeps-first-box"),
        ("lf-tree", "keeps-first-box"),
    },
    # The module builds each control's inputs and the instruction's current values,
    # which it restores per viewer from the tab's storage, so neither the rail's
    # members nor the words the instruction wraps exist before it runs. The
    # playground's own height is reserved (x-reserve), and the stage stands in its
    # region from first paint.
    "playground": {
        ("lf-playground-control", "keeps-first-box"),
        ("lf-playground-output", "keeps-first-box"),
        ("lf-playground-value", "keeps-first-box"),
    },
}
