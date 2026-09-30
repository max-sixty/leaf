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
    "diff": {("lf-diff", "keeps-first-box")},
    "gallery": {("lf-margin-entry-gallery", "keeps-first-box")},
    "playground": {
        ("lf-playground", "keeps-first-box"),
        ("lf-playground-control", "keeps-first-box"),
        ("lf-playground-output", "keeps-first-box"),
        ("lf-playground-preset", "example"),
        ("lf-playground-preview", "keeps-first-box"),
        ("lf-playground-setting", "example"),
        ("lf-playground-value", "keeps-first-box"),
    },
    "pr-review": {
        ("lf-call-diff", "keeps-first-box"),
        ("lf-pull-request", "keeps-first-box"),
    },
    "swipe": {
        ("lf-swipe-deck", "keeps-first-box"),
        ("lf-swipe-pile", "keeps-first-box"),
    },
    "targeting": {("lf-targeting", "keeps-first-box")},
    "visual-review": {("lf-visual-review", "keeps-first-box")},
}
