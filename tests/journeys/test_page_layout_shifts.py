"""The render gate carries passive page-code movement through to its findings."""

from model_folds import leaf_page

from leaf.render_gate.version import render_version


def test_render_version_reports_page_timer_movement(browser, serve):
    url = serve(
        leaf_page(
            "Shift",
            """
<h1 id="title">Shift</h1>
<div id="box">one line</div>
<p id="below">This paragraph moves every second and a half.</p>
<script>
  let n = 1;
  setInterval(() => {
    n = (n % 6) + 1;
    document.getElementById("box").innerHTML = "line<br>".repeat(n);
  }, 1500);
</script>
""",
        )
    )
    reading = render_version(browser.unwatched, url)
    shifts = [f for f in reading.advice if f.code == "passive-layout-shift"]
    assert any(f.at == "<p id=below>" for f in shifts), reading.findings
    assert not reading.failures, reading.failures
