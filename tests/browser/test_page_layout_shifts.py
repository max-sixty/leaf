"""Passive page-code movement reported by the render check."""

import pytest
from model_folds import leaf_page

from leaf.render_checks import evaluate_probe, observe_probe, rendered, wait_until_ready
from leaf.render_gate import readings


def test_passive_shifts_name_what_moved_inside_the_observation(browser, serve):
    """Movement before the observation is not its evidence, a node seen moving keeps
    its finding after it leaves the document, a source the browser doesn't expose
    names nothing, and a window in which nothing moves reports nothing."""
    page = browser.unwatched.new_page(viewport={"width": 1280, "height": 720})
    page.goto(
        serve(
            leaf_page(
                "Shift windows",
                '<div id="shadow" style="height:260px"></div>'
                '<div id="box" style="height:20px">Content</div>'
                '<p id="below">Reading position</p>',
            ),
            packages=(),
        )
    )
    wait_until_ready(page)
    # Native observers deliver together in one task. Wait for that delivery,
    # rather than a rendering turn, before removing a shifted source.
    page.locator("#shadow").evaluate("""el => {
      el.attachShadow({mode:'open'}).innerHTML =
        '<div id="grow" style="height:20px"></div><p>Shadow reading</p>';
      window.shiftDeliveries = [];
      new PerformanceObserver(list => {
        for (const entry of list.getEntries())
          for (const source of entry.sources)
            shiftDeliveries.push({id:source.node?.id, y:source.currentRect.y});
      }).observe({type:'layout-shift'});
    }""")
    rendered(page)

    def grow(height):
        expected = page.locator("#box").evaluate(
            """(el, height) => {
              shiftDeliveries = [];
              const y = document.getElementById('below').getBoundingClientRect().y
                + height - el.getBoundingClientRect().height;
              el.style.height = `${height}px`;
              document.getElementById('shadow').shadowRoot.getElementById('grow')
                .style.height = `${height}px`;
              return y;
            }""",
            height,
        )
        page.wait_for_function(
            "y => shiftDeliveries.some(s => s.id === 'below' && s.y === y)",
            arg=expected,
        )

    grow(80)
    before = page.locator("#below").bounding_box()["y"]
    with observe_probe(page, "passiveLayoutShifts") as passive:
        grow(140)
        # Attribution belongs to the painted movement even if a later revision
        # removes its source before the gate asks for the interval's findings: the
        # platform's source.node getter becomes null on detachment.
        page.locator("#below").evaluate("el => el.remove()")
    movement = next(finding for finding in passive if finding["at"] == "<p id=below>")
    assert movement["before"]["y"] == pytest.approx(before)
    assert movement["after"]["y"] == pytest.approx(before + 60)
    assert [finding["at"] for finding in passive] == ["<p id=below>"]
    with observe_probe(page, "passiveLayoutShifts") as unchanged:
        rendered(page)
    assert unchanged == []


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
    with readings.passive_layout_shift_advice(page) as found:
        pass
    assert bool(found) is not reserved
    if not reserved:
        assert any(f.at == "<p id=below>" for f in found)
        assert all(
            f.code == "passive-layout-shift" and f.severity == "advice" for f in found
        )
        assert any(f.values["before"]["y"] != f.values["after"]["y"] for f in found)
        assert found[0].values["observed_ms"] >= readings.PASSIVE_OBSERVATION_MS
