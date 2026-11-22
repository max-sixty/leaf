"""Tests scheduled by the measured cost of their boundary."""

from interact_support import PAGE, PAGE_GROUP, check, check_findings, found


def test_check_takes_a_stated_height_in_whole_css_pixels(page_dir):
    """`data-height` states the box of a widget that draws into one, in whole CSS
    pixels."""
    chart = '<lf-chart id="c" data-height="{}"><pre>{{ariaLabel: "x", marks: []}}</pre></lf-chart>'
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + chart.format(240))
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + chart.format("240px"))
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings, "allocation-value", attr="data-height", value="240px", allowed=None
    )


def test_check_advises_an_allocation_leaf_ignores_where_it_stands(page_dir):
    """An allocation means something only where the kernel's `$marks` say it does,
    and delivery paints none elsewhere, so the page would show no sign of it: a width
    on `main`, which would size the page, and a stated height on a block no module
    draws into. `page check` names each so the author can move it. A width on a table
    in the question's group, and a height on a chart, mean what they say. A tab set
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
            '<div id="sized" data-height="200">box</div>\n'
            '<lf-chart id="c" data-height="240"><pre>{ariaLabel: "x", marks: []}</pre>'
            "</lf-chart>\n  </lf-group>",
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    assert [
        (f.at, f.values["attr"], f.values["holds"], f.severity)
        for f in found(findings, "inert-allocation")
    ] == [
        ("<main>", "data-width", "content", "advice"),
        ("<div id=sized>", "data-height", "declared", "advice"),
        ("<lf-tabs id=page-tabs>", "data-width", "flow", "advice"),
    ]
