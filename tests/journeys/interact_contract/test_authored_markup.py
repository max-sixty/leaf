"""Tests scheduled by the measured cost of their boundary."""

from interact_support import PAGE, check, check_findings, found


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
