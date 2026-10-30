"""Charts and drawn figures: axis labels, theme colors, drawing for the room a chart
has, failed redraws, and inspecting a merge film by touch and keyboard."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_widgets import (
    CHART_IN_A_MESSAGE_PAGE,
    CHART_MARKS,
    CHART_PAGE,
    MESSAGE_CHART,
    chart_markup,
)
from render_harness import (
    ROOT,
    consume_browser_errors,
    leaf_page,
    names,
    open_page,
    plant_quiet_word,
    resized,
)

from browser.threads import open_panel_thread
from leaf import render_checks as render_checks_model

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_merge_film_inspection_has_touch_and_keyboard_routes(browser, serve):
    """Readable part details survive a tap, including a move across commit branches."""
    example = ROOT / "examples" / "wt-merge.html"
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
    inspect_next.focus()
    page.evaluate("window.scrollBy(0, 500)")
    inspect_next.press("i")
    details = inspector.bounding_box()
    assert details["y"] >= 0
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


# Charts. Every reading here is of the composed drawing rather than of the body it was
# built from: the body is Plot's options, and what the module owns is getting them to Plot
# and the drawing onto the page.
DREW = {
    # chart: (Plot's name for the mark group, shapes drawn, the element each is drawn as)
    "c-bars": ("bar", 6, "rect"),
    "c-rows": ("bar", 2, "rect"),
    "c-stack": ("bar", 4, "rect"),
    "c-line": ("line", 1, "path"),
    "c-dots": ("dot", 3, "circle"),
}


def test_covered_words_holds_a_tick_naming_its_month_on_a_second_line(browser, serve):
    """A dated axis names the month where one begins, on a line under the day: the tick
    for the first week of June reads 1 over Jun. Those two lines are two tspans of one
    <text>, offset by the dy the drawing asked for, and each reports a line box carrying
    the font's own leading — a couple of pixels taller than the step between them. So the
    pass hunting words drawn on other words read every such tick as a collision, on a
    drawing where no glyph comes near another, and the corpus's own heat-loss page failed
    the gate for drawing a perfectly ordinary axis.

    The reading is taken twice, as the float and the collapse are: once as the gate runs
    it, where the label's lines are held out, and once with that hold defeated, where it
    has to report. Otherwise a pass here would also be what a gate that never looked at
    the drawing returns. The two lines are pulled onto each other before either reading,
    so the second leg rests on an overlap this test arranged rather than on the leading
    the axis happens to be drawn with."""
    page = open_page(browser, serve(CHART_PAGE))
    # Vacuous otherwise: the page has to be carrying a tick that takes two lines.
    stacked = page.evaluate(
        """() => [...document.querySelectorAll('#c-line text')]
             .filter((t) => t.querySelectorAll('tspan').length > 1)
             .map((t) => t.textContent)"""
    )
    assert stacked, "no tick names its month on a second line, so nothing is held out"
    # The overlap the second reading needs belongs to the test rather than to whatever
    # leading Plot draws with: the month is pulled onto the day above it, so the two
    # boxes have to land on each other whatever step the drawing asked for. `held` does
    # not move, because the hold asks which label a line belongs to and not how far apart
    # a label's lines are.
    page.evaluate(
        """() => [...document.querySelectorAll('#c-line text')]
             .flatMap((t) => [...t.querySelectorAll('tspan')].slice(1))
             .forEach((line) => line.setAttribute('dy', '0'))"""
    )
    # The same named reading with its same-label hold disabled.
    held, reported = (
        render_checks_model.evaluate_probe(page, "coveredWords"),
        render_checks_model.evaluate_probe(
            page, "coveredWords", {"holdLabelLines": False}
        ),
    )
    assert held == []
    assert any(names(found, "c-line") for found in reported), (
        "the lines land on nothing, so a gate that never looked would pass this too"
    )


def test_the_covered_words_gate_still_reads_two_of_a_chart_s_labels_on_each_other(
    browser, serve
):
    """The other half of the exemption above, put back as a bug: a label's own lines are
    one run of words the drawing lays out together, and two labels landing on each other
    is the fault this pass exists to report. Arranged by placing one whole <text> on
    another rather than by spreading a label's lines, because the hold asks which <text>
    drew a line and not how far a line was moved.

    `<text>` is the case it is written for, being the near-miss that reads as one label
    and is not: every tick of an axis is a <text> inside one <g> inside one <svg>, so a
    hold reaching for either of those carries the whole drawing with it — every word of a
    chart stops being read against every other word of that chart — and nothing else in
    the suite would say so. The corpus sweeps and the copy assert this pass returns
    nothing, which a wider hold only makes more true, and the exemption above defeats the
    predicate wholesale, so it reports the same either way. The only existing bug-back on
    this pass reporting is the float's, and that is an HTML page whose runs never get an
    SVG label at all."""
    page = open_page(browser, serve(CHART_PAGE))
    # Two ticks the drawing places by transform, one stood on the other. The labels stay
    # whole, so what lands is two <text> elements rather than two lines of one.
    moved = page.evaluate(
        """() => {
            const ticks = [...document.querySelectorAll('#c-line text')]
                .filter((t) => t.hasAttribute('transform') && !t.querySelector('tspan'));
            if (ticks.length < 2) return null;
            ticks[1].setAttribute('transform', ticks[0].getAttribute('transform'));
            return [ticks[0].textContent, ticks[1].textContent];
        }"""
    )
    assert moved, "no two ticks the drawing places by transform, so nothing was stacked"
    # The root scrollport must not hide page-content collisions from this reading,
    # whether the chart starts below the fold or the user has scrolled to it.
    for scrolled in (False, True):
        if scrolled:
            page.locator("#c-line").scroll_into_view_if_needed()
        covered = render_checks_model.evaluate_probe(page, "coveredWords")
        assert [f for f in covered if {f["words"], f["covered"]} == set(moved)], (
            f"two of a chart's labels stood on each other unreported: {covered}",
            scrolled,
        )


def test_covered_words_reads_only_the_visible_svg_state(browser, serve):
    """A timing study replaces overlapping SVG labels by hiding their group."""
    page = open_page(
        browser,
        serve("""<!doctype html><html><head><title>SVG states</title></head><body><main>
          <svg id="states" viewBox="0 0 500 80">
            <text x="10" y="30">Editing the proposal</text>
            <g id="saved-state" style="display:none">
              <text x="10" y="30">Original words restored</text>
            </g>
          </svg></main></body></html>"""),
    )
    assert render_checks_model.evaluate_probe(page, "coveredWords") == []
    page.locator("#saved-state").evaluate("node => node.style.display = 'inline'")
    assert render_checks_model.evaluate_probe(page, "coveredWords")
    page.locator("#saved-state").evaluate("node => node.style.display = 'none'")
    assert render_checks_model.evaluate_probe(page, "coveredWords") == []


def test_a_chart_wears_the_page_s_colors_and_turns_over_with_the_scheme(browser, serve):
    """A series takes the theme's token, `var(--series-N)`, which Plot writes into the
    drawing as it was given. Resolved to a value in JavaScript it would freeze the scheme
    the browser was in when the chart was drawn: a copy exported from a light window
    opens as a light slab for a dark user, and a scheme flipped mid-read leaves the
    drawing behind. So this asserts both halves: that each series is painted the token it
    names, and that no hex colour was written into the drawing at all. The flip is made
    with no reload, so the nodes under it are the same nodes; a drawing that had been
    painted values would fail here and pass every static check.

    Before that, two readings of the same page. A chart that drew nothing still has a
    box and no console error, so the render gate passes it: each body makes a different
    shape of call — rows handed to a mark, a faceted mark, marks stacked by Plot, a line
    over ISO dates on a time scale, dots — and each is counted rather than merely found,
    because a call that lost its data would still draw axes. And a drawing is one
    picture named by its author's `ariaLabel`: Plot names every group inside it too, on
    <g> elements carrying no role, which axe reports as a serious failure, so those
    names are kept as data a test can still ask for."""
    page = open_page(browser, serve(CHART_PAGE))
    for widget, (part, count, tag) in DREW.items():
        drew = page.evaluate(CHART_MARKS, widget)
        assert drew, f"{widget} drew nothing at all"
        shapes = drew["marks"].get(part, [])
        assert [shape[0] for shape in shapes] == [tag] * count, (widget, drew["marks"])

    drawing = page.locator("#c-bars svg[role=img]")
    assert drawing.get_attribute("aria-label") == (
        "Merged by quarter: apps 12, 19, 14; infra 7, 11, 17"
    )
    assert (
        page.evaluate("() => document.querySelectorAll('#c-bars g[aria-label]').length")
        == 0
    )
    assert (
        page.evaluate(
            "() => document.querySelectorAll('#c-bars g[data-lf-part=bar]').length"
        )
        > 0
    )
    # A colour ramp beside the drawing is an <svg> too, and not the picture.
    ramp = page.evaluate(
        """() => [...document.querySelectorAll('#c-dots .lf-chart-drawing svg')]
             .map((svg) => svg.getAttribute('role'))"""
    )
    assert ramp.count("img") == 1 and len(ramp) > 1, ramp
    assert (
        page.locator("#c-dots svg[role=img]").get_attribute("aria-label")
        == "Review minutes against lines changed: 12 and 4, 90 and 26, 310 and 71"
    )

    def worn():
        drew = page.evaluate(CHART_MARKS, "c-bars")
        assert drew["painted"] == [], drew["painted"]
        fills = [fill for _, fill, _ in drew["marks"]["bar"]]
        return drew["tokens"], fills

    # Provider legend defaults yield to the page face without a JS inline repair.
    page.add_style_tag(content=":root { --sans: Georgia; }")
    legend = page.locator('#c-bars [class*="-swatches"]').first
    expect(legend).to_have_count(1)
    assert legend.evaluate("node => getComputedStyle(node).fontFamily") == "Georgia"
    assert legend.evaluate("node => node.style.fontFamily") == ""

    tokens, fills = worn()
    assert tokens[0] != tokens[1], "two series wearing one colour proves nothing"
    assert sorted(set(fills)) == sorted(tokens), (tokens, fills)

    page.emulate_media(color_scheme="dark")
    dark, fills = worn()
    assert dark != tokens, "the dark palette must differ, or the flip proves nothing"
    assert sorted(set(fills)) == sorted(dark), (dark, fills)
    # And the paper Plot fills its halos and tips with is the page's, not its white.
    assert (
        page.evaluate(
            """() => getComputedStyle(document.querySelector('#c-bars svg[role=img]'))
             .getPropertyValue('--plot-background').trim()"""
        )
        != "white"
    )


def test_a_chart_preserves_authored_inline_presentation_over_provider_defaults(
    browser, serve
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Authored chart",
                "<h1>Authored chart</h1>"
                + chart_markup(
                    "authored-chart",
                    """{
      ariaLabel: "One value", style: {fontSize: "23px", background: "papayawhip"},
      marks: [Plot.dot([{x:1,y:2}], {x:"x",y:"y"})]
    }""",
                ),
            )
        ),
    )
    svg = page.locator('#authored-chart svg[role="img"]')
    expect(svg).to_be_visible()
    assert svg.evaluate("node => getComputedStyle(node).fontSize") == "23px"
    assert (
        svg.evaluate("node => getComputedStyle(node).backgroundColor")
        == "rgb(255, 239, 213)"
    )


def test_a_chart_is_drawn_for_the_room_it_has_rather_than_scaled_into_it(
    browser, serve
):
    """A drawing that scales takes its labels with it. That is what a diagram does, and
    at 63% of its natural size a five-node flowchart's labels went under legibility; a
    chart has no natural size to keep, so it is drawn again for the width it now has and
    its text stays the size the theme set. The room changes for reasons a user never
    asked about — a window narrower than the column, the thread panel taking its strip
    out of one — so this is the ordinary case rather than a window somebody dragged.

    The body is JavaScript, so what Plot takes as a function reaches it as one — here a
    tick format — and the body reads the width the host draws at, which is how it fits
    its labels to the room: the wider label is shown only if the body was handed the
    width. And the redraw replaces only the drawing's own box, so a word the runtime
    hangs on the chart, a child of the element, survives it."""
    page = open_page(browser, serve(CHART_PAGE))
    ticks = page.locator(
        '#c-stack [data-lf-part="y-axis tick label"] text'
    ).all_text_contents()
    assert ticks and all(tick.endswith("h") for tick in ticks), ticks
    assert page.evaluate(CHART_MARKS, "c-rows")["room"] > 500
    expect(page.locator('#c-rows [data-lf-part="x-axis label"]')).to_contain_text(
        "open issues"
    )
    before = page.evaluate(CHART_MARKS, "c-bars")
    assert before["width"] == before["room"], before

    # A retained chart may leave and re-enter during document reconciliation. Its
    # drawing survives the move, and must keep responding to the room it has.
    page.evaluate("""() => lfUnwatched(() => {
        const chart = document.getElementById('c-bars');
        const parent = chart.parentNode;
        const next = chart.nextSibling;
        chart.remove();
        parent.insertBefore(chart, next);
    })""")
    plant_quiet_word(page, "#c-bars", "")
    notes = "() => document.getElementById('c-bars').querySelectorAll('.lf-ui').length"
    held = page.evaluate(notes)
    assert held > 0, "the chart holds no word of the runtime's"

    # Narrower than the column, which is where the room actually changes: the column is
    # capped, so a wider window leaves a chart exactly where it was. Read during resize
    # delivery, before paint: waiting for settlement would hide one frame of shrunken
    # labels from an SVG still drawn for the preceding width.
    page.evaluate("""() => {
        window.chartResizeReadings = [];
        window.chartResizeWatch = new ResizeObserver(entries => {
            for (const {target} of entries) {
                const svg = target.querySelector('svg[role=img]');
                chartResizeReadings.push({
                    room: Math.round(target.clientWidth),
                    width: Number(svg.getAttribute('width')),
                });
            }
        });
        chartResizeWatch.observe(document.getElementById('c-bars'));
    }""")
    resized(page, 620, 900)
    page.wait_for_function(
        """(id) => {
            const el = document.getElementById(id);
            const svg = el.querySelector('svg[role=img]');
            return svg && Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
        }""",
        arg="c-bars",
    )
    after = page.evaluate(CHART_MARKS, "c-bars")
    assert after["room"] < before["room"], (before, after)
    readings = page.evaluate("""() => {
        chartResizeWatch.disconnect();
        return chartResizeReadings;
    }""")
    assert any(reading["room"] == after["room"] for reading in readings), readings
    assert all(reading["width"] == reading["room"] for reading in readings), readings
    # The painted box of a tick label, not its computed font-size: a drawing scaled by its
    # viewBox keeps the same computed size and renders smaller, so the property this test
    # is about is invisible to the one reading and plain in the other.
    assert after["tick"] == before["tick"], (before, after)
    assert page.evaluate(notes) == held, "the redraw took the runtime's word away"


def test_a_chart_draws_into_the_box_its_data_height_states(browser, serve):
    """The page lays a chart's box out before Plot draws (x-height), so the drawing fills
    that box rather than sizing it: with a legend Plot sets above it, the legend and the
    drawing together end at the box's foot, and the box keeps the height it had at first
    paint. Drawn at the options' own height instead, the legend overhangs the box."""
    body = """{
  ariaLabel: "Merged by team: backend 12, frontend 19",
  color: {legend: true, range: ["var(--series-1)", "var(--series-2)"]},
  marks: [Plot.barY([{team: "backend", n: 12}, {team: "frontend", n: 19}],
                    {x: "team", y: "n", fill: "team"})],
}"""
    source = leaf_page(
        "tall chart",
        '<h1 id="t">Merged</h1>\n'
        + chart_markup("c-tall", body).replace(
            '<lf-chart id="c-tall">', '<lf-chart id="c-tall" data-height="240">'
        ),
    )
    page = open_page(browser, serve(source))
    box = page.evaluate(
        """() => {
            const el = document.getElementById('c-tall');
            const own = el.getBoundingClientRect();
            const drawing = el.querySelector('.lf-chart-drawing').getBoundingClientRect();
            const svg = el.querySelector('svg[role=img]').getBoundingClientRect();
            return {height: own.height, bottom: own.bottom,
                    drawing: drawing.bottom, svg: svg.bottom,
                    legends: el.querySelectorAll('svg:not([role=img]), div[class$=swatches]').length};
        }"""
    )
    assert box["height"] == 240, box
    assert box["legends"], box
    assert box["svg"] == box["drawing"] == box["bottom"], box
    # The drawing keeps its height even before resize delivery redraws it, so measuring
    # the new room cannot move everything below the chart.
    narrowed = page.evaluate(
        """() => {
            const el = document.getElementById('c-tall');
            el.style.width = `${el.clientWidth / 2}px`;
            return el.getBoundingClientRect().height;
        }"""
    )
    assert narrowed == 240, narrowed


def test_a_chart_keeps_its_stated_height_beside_a_taller_one(browser, serve):
    """A row of tiles stretches each cell to the row's tallest, and once a chart is drawn
    its box is the drawing's, so a short chart's box stands as tall as its neighbour.
    Drawn again for a new width, it keeps the height it states. Drawn to the stretched
    box, it took the neighbour's height, and each width change after kept it there."""
    body = """{
  ariaLabel: "Merged by team: backend 12, frontend 19",
  marks: [Plot.barY([{team: "backend", n: 12}, {team: "frontend", n: 19}],
                    {x: "team", y: "n"})],
}"""
    tiles = "".join(
        chart_markup(chart_id, body).replace(
            f'<lf-chart id="{chart_id}">',
            f'<lf-chart id="{chart_id}" data-height="{height}">',
        )
        for chart_id, height in (("c-short", 200), ("c-tall", 420))
    )
    source = leaf_page(
        "tiled charts",
        f'<h1 id="t">Merged</h1><div class="layout-tiles">{tiles}</div>',
    )
    page = open_page(browser, serve(source))
    heights = """() => Object.fromEntries(['c-short', 'c-tall'].map(id => [id,
        Number(document.querySelector(`#${id} svg[role=img]`).getAttribute('height'))]))"""
    drawn_for_room = """() => ['c-short', 'c-tall'].every(id => {
        const el = document.getElementById(id);
        const svg = el.querySelector('svg[role=img]');
        return Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
    })"""
    assert page.evaluate(heights) == {"c-short": 200, "c-tall": 420}
    widths = []
    for width in (640, 1280):
        resized(page, width, 900)
        page.wait_for_function(drawn_for_room)
        widths.append(page.locator("#c-short").evaluate("el => el.clientWidth"))
    assert widths[0] != widths[1], "the charts were never drawn again"
    assert page.evaluate(heights) == {"c-short": 200, "c-tall": 420}


def test_a_chart_that_fails_on_a_redraw_stays_failed_when_it_returns(browser, serve):
    """A body may draw at one width and fail at another. The redraw that fails puts the
    refusal where the drawing was, and the refusal stands: a chart that leaves the page
    and returns, as document reconciliation moves it, does not watch its room again,
    paint into the drawing the refusal replaced, or tell the author a second time."""
    body = '{ariaLabel: "merged", marks: [width < 560 ? Plot.barz() : Plot.ruleY([0])]}'
    source = leaf_page(
        "narrow chart",
        f'<h1 id="t">Narrow</h1>\n<lf-chart id="c-narrow"><pre>\n{body}\n</pre></lf-chart>',
    )
    page = open_page(browser, serve(source))
    page.wait_for_function("() => document.querySelector('#c-narrow svg[role=img]')")
    resized(page, 480, 900)
    expect(page.locator("#c-narrow .lf-error")).to_contain_text("Plot.barz")
    returned = page.evaluate("""async () => {
        const chart = document.getElementById('c-narrow');
        const failure = chart.querySelector('.lf-error');
        const parent = chart.parentNode;
        const next = chart.nextSibling;
        chart.remove();
        await new Promise((resolve) => setTimeout(resolve));
        parent.insertBefore(chart, next);
        for (let i = 0; i < 3; i++) await new Promise(requestAnimationFrame);
        return chart.querySelector('.lf-error') === failure;
    }""")
    assert returned, "the returning chart drew its failure again"
    errors = consume_browser_errors(page, '<lf-chart id="c-narrow"> failed: ')
    assert len(errors) == 1, errors


def test_a_chart_in_a_closed_thread_draws_at_its_visible_width_when_opened(
    browser, serve
):
    """A chart an agent sends in a reply is markup like any other, which is why the body
    is JSON rather than a script: a message carries no module. While its thread is
    closed it has no box, and it must draw at its visible width once the user opens the
    thread in the panel.

    Read the visible drawing after the thread opens; an intermediate absence of SVG
    cannot distinguish a closed thread from a drawing that has not finished.
    """
    url = serve(CHART_IN_A_MESSAGE_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-chart",
            "author": "user",
            "revision": 1,
            "text": "How did the quarter go?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-chart",
            "revision": 1,
            "text": "Like this:",
            "markup": chart_markup("msg-chart", MESSAGE_CHART),
        },
    )
    page = open_page(browser, url)
    assert (
        page.evaluate("() => document.getElementById('msg-chart')?.clientWidth ?? 0")
        == 0
    ), "the thread must be closed, or there was a box all along"

    open_panel_thread(page, "c-chart")
    expect(page.locator("#msg-chart svg[role=img]")).to_be_visible()
    page.wait_for_function(
        """() => {
            const el = document.getElementById('msg-chart');
            const svg = el.querySelector('svg[role=img]');
            return svg && Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
        }"""
    )
    drawn = page.evaluate(CHART_MARKS, "msg-chart")
    assert drawn["room"] > 100, drawn
    assert len(drawn["marks"]["bar"]) == 2, drawn


def test_a_chart_in_a_shut_tab_draws_when_the_tab_opens(browser, serve):
    """A shut tab's panel is skipped content, whose rect the browser lays out on request,
    so a chart there must not take that rect as its room: it waits for the user to open
    the tab, and its bundle waits with it, whichever of its module and the tab set's
    upgrades first."""
    url = serve(
        leaf_page(
            "chart in a shut tab",
            '<h1 id="t">Views</h1><lf-tabs id="views">'
            '<lf-tab id="words" label="Words"><p id="p">Some words.</p></lf-tab>'
            '<lf-tab id="numbers" label="Numbers">'
            f"{chart_markup('tab-chart', MESSAGE_CHART)}</lf-tab></lf-tabs>",
        )
    )
    context = browser.new_context()

    # The chart's module is held until the tab set has hidden its panel, the order in
    # which reading its rect would draw it.
    def late(route):
        expect(
            route.request.frame.page.locator('#numbers[hidden="until-found"]')
        ).to_be_attached()
        route.continue_()

    context.route("**/lf-chart.js", late)
    page = open_page(browser, url, context=context)
    expect(page.locator("#views.lf-rendered")).to_be_attached()
    expect(page.locator("#tab-chart svg")).to_have_count(0)
    assert not page.evaluate(
        "() => performance.getEntriesByType('resource')"
        ".some((entry) => entry.name.includes('plot.esm'))"
    ), "the shut tab's chart loaded its bundle"

    page.get_by_role("tab", name="Numbers").click()
    expect(page.locator("#tab-chart svg[role=img]")).to_be_visible()
