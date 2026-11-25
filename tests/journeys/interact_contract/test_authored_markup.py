"""Tests scheduled by the measured cost of their boundary."""

from interact_support import PAGE, PAGE_GROUP, check_findings, found


def test_check_advises_an_allocation_leaf_ignores_where_it_stands(page_dir):
    """An allocation means something only where the kernel's `$marks` say it does,
    and delivery paints none elsewhere, so the page would show no sign of it: a width
    on `main`, which would size the page. `page check` names it so the author can move
    it. A width on a table in the question's group means what it says. A tab set
    draws no box of its own only where
    it is written `flow="page"`, so a width there means nothing and on a boxed set it
    holds."""
    tabs = (
        '<lf-tabs id="{id}"{flow} data-width="wide">'
        '<lf-tab id="{id}-one" label="One"><p>One.</p></lf-tab></lf-tabs>'
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<main>", '<main data-width="wide">')
        .replace(
            "</section>",
            "</section>"
            + tabs.format(id="page-tabs", flow=' flow="page"')
            + tabs.format(id="boxed-tabs", flow=""),
        )
        .replace(PAGE_GROUP, '<lf-options id="plan-choice">')
        .replace(
            "</lf-options>\n  </lf-group>",
            "</lf-options>\n"
            '<table id="kept" data-width="wide"><tr><td>A</td></tr></table>\n'
            "  </lf-group>",
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    assert [
        (f.at, f.values["attr"], f.values["holds"], f.severity)
        for f in found(findings, "inert-allocation")
    ] == [
        ("<main>", "data-width", "content", "advice"),
        ("<lf-tabs id=page-tabs>", "data-width", "flow", "advice"),
    ]
