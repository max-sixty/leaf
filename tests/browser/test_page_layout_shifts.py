"""Passive page-code movement reported by the render check."""

import pytest
from model_folds import leaf_page

from leaf.render_checks import evaluate_probe, rendered, wait_until_ready
from leaf.render_gate import readings


@pytest.mark.parametrize("reserved", [False, True])
def test_render_check_reports_delayed_page_layout_shifts(browser, serve, reserved):
    url = serve(
        leaf_page(
            "Shift",
            """
<h1 id="title">Shift</h1>
<div id="box">one line</div>
<p id="below">This paragraph must keep its place.</p>
""",
        )
    )
    page = browser.unwatched.new_page(viewport={"width": 1280, "height": 720})
    try:
        page.goto(url)
        wait_until_ready(page)
        rendered(page)
        if reserved:
            page.locator("#box").evaluate("el => el.style.height = '160px'")
            rendered(page)
        # Load probes before arming the author's timer, so its first tick is inside
        # the observation even on a busy host. The actual paints use Chrome's clock.
        evaluate_probe(page, "unreducedMotion")
        page.evaluate("""() => {
          let n = 1;
          window.shiftTimer = setInterval(() => {
            n = (n % 6) + 1;
            document.getElementById('box').innerHTML = 'line<br>'.repeat(n);
          }, 1500);
        }""")
        found = readings.passive_layout_shift_advice(page)
        assert bool(found) is not reserved
        if not reserved:
            assert any(f.at == "<p id=below>" for f in found)
            assert all(
                f.code == "passive-layout-shift" and f.severity == "advice"
                for f in found
            )
            assert any(f.values["before"]["y"] != f.values["after"]["y"] for f in found)
            assert "3000ms" in str(found[0])
    finally:
        page.close()
