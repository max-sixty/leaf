"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.margin import PANE_PIN_PAGE, _comment_on
from render_harness import margins_laid_out, open_page, pane_scroll_behavior, resized

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("engine", ["firefox_browser", "webkit_browser"])
def test_rows_follow_a_pane_and_a_shadow_scroller_in_every_engine(
    request, serve, engine
):
    """Firefox and WebKit carry rows on the same anchors as Chrome: a pin in a pane,
    whose lane is a frame anchored to the pane's scroller, and a row whose target
    scrolls inside a widget's shadow tree, anchored through the part the document
    names it by. Both keep their offset from their targets through those scrolls."""
    browser = request.getfixturevalue(engine)
    page = open_page(browser, serve(PANE_PIN_PAGE, events=[_comment_on("pane-top")]))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    page.evaluate(
        """async () => {
          const {registerContribution} = await window.__lfWidgetApi();
          const host = document.createElement('div');
          const root = host.attachShadow({mode: 'open'});
          root.innerHTML = '<div id="inner" style="height: 100px; overflow: auto">'
            + '<div style="height: 40px"></div><p id="deep">Deep target</p>'
            + '<div style="height: 400px"></div></div>';
          document.querySelector('#other-pane > div').prepend(host);
          const target = root.getElementById('deep');
          const margin = registerContribution({key: 'deep', target,
            read: () => ({entries: [{
              key: 'deep', glyph: '!', label: 'deep controls'}]}),
            activate: () => {}});
          window.__deep = {target, margin, inner: root.getElementById('inner')};
        }"""
    )
    margins_laid_out(page)
    reading = """() => {
      const pane = document.querySelector('[data-lf-margin-for="pane-top"]');
      const {target, margin} = window.__deep;
      const deep = margin.control('deep', 'margin').closest('.lf-margin-cluster');
      const top = (a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top;
      return {pane: top(pane, document.getElementById('pane-top')),
              deep: top(deep, target),
              shown: !pane.classList.contains('lf-withheld')
                && !deep.classList.contains('lf-withheld')};
    }"""
    before = page.evaluate(reading)
    assert before["shown"], before
    page.evaluate("""() => {
      document.querySelector('#pin-pane > div').scrollTop = 40;
      window.__deep.inner.scrollTop = 20;
    }""")
    rendered(page)
    after = page.evaluate(reading)
    assert after["shown"], after
    assert after["pane"] == pytest.approx(before["pane"], abs=1), (before, after)
    assert after["deep"] == pytest.approx(before["deep"], abs=1), (before, after)
