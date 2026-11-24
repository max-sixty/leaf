"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.widgets.test_charts import (
    CASE_SCALES,
    POINTER_CASES,
    POINTER_PAGE,
    _picked,
    _says_plot_s_rows,
)
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import consume_browser_errors, open_page

from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_merge_film_inspection_has_touch_and_keyboard_routes(browser, serve):
    """Readable part details survive a tap, including a move across commit branches."""
    example = named_source("wt-merge")
    context = browser.new_context(
        viewport={"width": 320, "height": 844}, has_touch=True
    )
    page = open_page(browser, live_url(serve(example)), context=context)
    film = page.locator("lf-merge-film")
    inspector = film.locator(".film-inspect")
    inspect_next = film.get_by_role("button", name="Inspect next element")
    graph = film.locator("svg:visible")
    commits = graph.locator('g[data-label^="commit "]')
    first, last = commits.first, commits.last
    labels = [first.get_attribute("data-label"), last.get_attribute("data-label")]
    assert labels[0] != labels[1]
    # Read at the end of the actual click, before later provider work can turn an
    # initially empty response into an eventual success.
    inspect_next.evaluate("""button => button.addEventListener('click', () => {
      const inspector = button.closest('lf-merge-film').querySelector('.film-inspect');
      window.firstInspection = {
        hidden: inspector.hidden,
        title: inspector.querySelector('strong').textContent,
      };
    }, {once: true})""")
    inspect_next.scroll_into_view_if_needed()
    inspection_top = inspect_next.bounding_box()["y"]
    inspect_next.tap()
    assert inspect_next.bounding_box()["y"] == pytest.approx(inspection_top, abs=1)
    assert page.evaluate("firstInspection") == {"hidden": False, "title": labels[0]}
    inspect_next.press("Escape")
    expect(inspector).to_be_hidden()
    for part, label in zip([first, last], labels, strict=True):
        part.locator("circle").tap()
        expect(inspector).to_be_visible()
        expect(inspector.locator("strong")).to_have_text(label)
        expect(inspector.locator("span")).to_have_text(part.get_attribute("data-info"))
        expect(film.locator(".film-play")).to_have_text("Play")
    graph.tap(position={"x": 3, "y": 3})
    expect(inspector).to_be_hidden()
    inspect_next.tap()
    expect(inspector).to_be_visible()
    expect(inspector.locator("strong")).to_have_text(labels[0])
    assert inspect_next.bounding_box()["height"] >= 44
    # Cycling to worktree details keeps both the reader and the cycle control in view.
    for _ in range(9):
        inspect_next.tap()
    expect(inspector.locator("strong")).to_have_text("worktree ~/repo.feature")
    details = inspector.bounding_box()
    assert details["y"] >= 0
    reading_bottom = page.evaluate(
        "async () => (await window.__lfWidgetApi()).shownWindow().bottom"
    )
    assert details["y"] + details["height"] <= reading_bottom
    assert inspect_next.bounding_box()["y"] >= 0
    play = film.locator(".film-play")
    play.focus()
    play_top = play.bounding_box()["y"]
    play.press("i")
    assert play.bounding_box()["y"] == pytest.approx(play_top, abs=1)
    expect(inspector).to_be_visible()
    play.press("Escape")
    expect(inspector).to_be_hidden()
    play.press("i")
    expect(inspector).to_be_visible()
    scrub = film.get_by_role("slider", name="Film position")
    scrub.focus()
    scrub.press("End")
    expect(inspector).to_be_hidden()
    expect(play).to_have_text("Replay")
    assert float(scrub.input_value()) == pytest.approx(
        float(scrub.get_attribute("max"))
    )
    scrub.press("Home")
    expect(scrub).to_have_value("0")
    expect(play).to_have_text("Play")
    play.focus()
    play.press("ArrowRight")
    play.press("i")
    expect(inspector).to_be_visible()
    play.press("ArrowRight")
    expect(inspector).to_be_hidden()
    play.press("i")
    expect(inspector).to_be_visible()
    film.locator(".film-settings summary").tap()
    film.get_by_label("--no-squash", exact=True).check()
    expect(inspector).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_chart_picks_the_point_plot_s_own_pointer_picks(engine, request, serve):
    """At every place over a chart, the chart reads the datum Plot's own pointer picks
    for the same chart, and stands its ring where Plot's tip points: across facets,
    each judged in its own frame; on a dot anchored to the frame's foot; along y where
    the author named y; along x on bars, where no tip was named; of two marks, the one
    whose pick stands nearer; of one data drawn twice, by either mark's own rule and
    reach; by a tip's own px, on a scale that transforms it too; and on a stacked
    segment, at the middle of its extent. It says each row Plot's tip says there, a
    line for each as Plot's tip draws it: the row's own label, then the value a tip's
    format gives it, or none where the format gives nothing. A mark its offsets moved
    is read where Plot draws it, which Plot's own pointer misses."""
    page = open_page(request.getfixturevalue(engine), serve(POINTER_PAGE))
    steps = [(n / 11, m / 7) for n in range(1, 11) for m in range(1, 7)]
    for name, (_, alone) in POINTER_CASES.items():
        chart = page.locator(f"#{name} svg[role=img]")
        expect(chart).to_be_visible()
        page.evaluate(
            """async ([name, marks, scales, width, height]) => {
              const {Plot} = await import('/vendor/plot.esm.js');
              const options = new Function('Plot', `return {${scales}marks: [${marks}]};`)(Plot);
              const figure = Plot.plot({...options, width, height});
              figure.id = `${name}-alone`;
              const chart = document.getElementById(name);
              chart.after(figure);
              chart.scrollIntoView({block: 'start'});
            }""",
            [
                name,
                alone,
                CASE_SCALES.get(name, ""),
                float(chart.get_attribute("width")),
                float(chart.get_attribute("height")),
            ],
        )
        ours, plots = (
            chart.bounding_box(),
            page.locator(f"#{name}-alone").bounding_box(),
        )
        differ = []
        for fx, fy in steps:
            # Plot's tip reads each place afresh, so the chart is probed from where no
            # reading stands. A probe slower than the page's dwell shows the chart's
            # preview, which holds its point while the pointer crosses empty drawing and
            # until the pointer has been off the chart for a dwell, and puts the ring
            # away in the rendering pass after that.
            page.wait_for_function(
                """(name) => !document.getElementById('lf-preview').matches(':popover-open')
                  && !document.querySelector(`#${name} .lf-chart-at:not([display=none])`)""",
                arg=name,
            )
            [mine] = _picked(page, f"#{name} svg[role=img]", ours, fx, fy) or [None]
            tips = _picked(page, f"#{name}-alone", plots, fx, fy)
            aim = [plots["width"] * fx, plots["height"] * fy]
            # Of the tips Plot shows, the one standing nearest the pointer.
            expected = min(
                tips,
                key=lambda tip: (
                    (tip["at"][0] - aim[0]) ** 2 + (tip["at"][1] - aim[1]) ** 2
                ),
                default=None,
            )
            # Plot rounds its tip's anchor to a whole pixel and shifts it half of one
            # for crisp edges.
            if (mine is None) != (expected is None) or (
                mine
                and expected
                and (
                    not _says_plot_s_rows(mine["lines"], expected["rows"])
                    or max(
                        abs(a - b)
                        for a, b in zip(mine["at"], expected["at"], strict=True)
                    )
                    > 1.5
                )
            ):
                differ.append((round(fx, 2), round(fy, 2), mine, expected))
        assert not differ, f"{name}: {differ}"
        page.mouse.move(2, 2)

    moved = page.locator("#moved")
    moved.evaluate("el => el.scrollIntoView({block: 'start'})")
    dots = moved.locator("[data-lf-plot=dot] circle").all()
    for circle, name in zip(dots, ["p", "q", "r"], strict=True):
        dot = circle.bounding_box()
        center = (dot["x"] + dot["width"] / 2, dot["y"] + dot["height"] / 2)
        page.mouse.move(center[0] + 3, center[1] + 3)
        page.mouse.move(*center)
        expect(moved.locator(".lf-chart-at circle")).to_be_visible()
        ring = moved.locator(".lf-chart-at circle").bounding_box()
        assert ring
        assert abs(ring["x"] + ring["width"] / 2 - center[0]) <= 1.5, name
        assert abs(ring["y"] + ring["height"] / 2 - center[1]) <= 1.5, name
        assert moved.evaluate("el => el.lfPreview()?.name") == name
    # Plot's own tip, drawn beside each chart to compare with, restates its facet's
    # transform as it moves: Plot's write, not the chart's.
    consume_browser_errors(
        page,
        lambda problem: (
            problem.code == "unchanged-write"
            and "-alone" in " ".join(problem.values.get("node", []))
        ),
    )
