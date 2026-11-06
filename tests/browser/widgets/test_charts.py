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
    PREVIEW,
    consume_browser_errors,
    leaf_page,
    long_press,
    names,
    open_page,
    plant_quiet_word,
    resized,
)

from browser.threads import open_panel_thread
from leaf import render_checks as render_checks_model
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


def test_the_covered_words_gate_reads_a_chart_s_labels_and_what_is_shown(
    browser, serve, subtests
):
    """The pass hunting words drawn on other words holds a label's own lines out, still
    reports two labels on each other, and reads only the SVG state showing. The cases run
    in this order on one drawing, since the first needs the page free of findings and
    each later one adds its own."""
    page = open_page(browser, serve(CHART_PAGE))

    with subtests.test("only the visible SVG state"):
        # A timing study replaces overlapping SVG labels by hiding their group.
        page.evaluate(
            """() => {
              const box = document.createElement('div');
              box.id = 'states';
              box.innerHTML = `<svg viewBox="0 0 500 80">
                <text x="10" y="30">Editing the proposal</text>
                <g id="saved-state" style="display:none">
                  <text x="10" y="30">Original words restored</text>
                </g></svg>`;
              document.querySelector('main').append(box);
            }"""
        )
        assert render_checks_model.evaluate_probe(page, "coveredWords") == []
        page.locator("#saved-state").evaluate("node => node.style.display = 'inline'")
        assert render_checks_model.evaluate_probe(page, "coveredWords")
        page.locator("#saved-state").evaluate("node => node.style.display = 'none'")
        assert render_checks_model.evaluate_probe(page, "coveredWords") == []
        page.locator("#states").evaluate("box => box.remove()")

    with subtests.test("a tick naming its month on a second line"):
        # A dated axis names the month where one begins, on a line under the day: the
        # tick for the first week of June reads 1 over Jun. Those two lines are two
        # tspans of one <text>, offset by the dy the drawing asked for, and each reports
        # a line box carrying the font's own leading, a couple of pixels taller than
        # the step between them. So the pass read every such tick as a collision, and
        # the corpus's own heat-loss page failed the gate for an ordinary axis.
        #
        # The reading is taken as the gate runs it, where the label's lines are held out,
        # and with that hold defeated, where it has to report; otherwise a pass here
        # would also be what a gate that never looked at the drawing returns. Vacuous
        # otherwise: the page has to be carrying a tick that takes two lines.
        stacked = page.evaluate(
            """() => [...document.querySelectorAll('#c-line text')]
                 .filter((t) => t.querySelectorAll('tspan').length > 1)
                 .map((t) => t.textContent)"""
        )
        assert stacked, (
            "no tick names its month on a second line, so nothing is held out"
        )
        # The overlap the second reading needs belongs to the test rather than to
        # whatever leading Plot draws with: the month is pulled onto the day above it,
        # so the two boxes land on each other whatever step the drawing asked for. `held`
        # does not move, because the hold asks which label a line belongs to and not how
        # far apart a label's lines are.
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

    with subtests.test("two of a chart's labels on each other"):
        # The other half of that exemption, put back as a bug: a label's own lines are
        # one run of words the drawing lays out together, and two labels landing on each
        # other is the fault this pass exists to report. Arranged by placing one whole
        # <text> on another rather than by spreading a label's lines, because the hold
        # asks which <text> drew a line and not how far a line was moved.
        #
        # `<text>` is the case it is written for: every tick of an axis is a <text>
        # inside one <g> inside one <svg>, so a hold reaching for either of those
        # carries the whole drawing with it, every word of a chart no longer read against
        # every other, and nothing else in the suite would say so. The corpus sweeps
        # assert this pass returns nothing, which a wider hold only makes more true.
        moved = page.evaluate(
            """() => {
                const ticks = [...document.querySelectorAll('#c-line text')]
                    .filter((t) => t.hasAttribute('transform') && !t.querySelector('tspan'));
                if (ticks.length < 2) return null;
                ticks[1].setAttribute('transform', ticks[0].getAttribute('transform'));
                return [ticks[0].textContent, ticks[1].textContent];
            }"""
        )
        assert moved, (
            "no two ticks the drawing places by transform, so nothing was stacked"
        )
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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_chart_gives_its_legend_the_room_a_late_font_takes(engine, request, serve):
    """A legend's height comes from its type as well as its width: a font that arrives
    after the chart has drawn, as the wider spacing set here does, wraps the swatches
    onto more lines at the same width. The drawing gives the legend that room and still
    ends at the box's foot. Measured once per width, the legend ran past the box onto
    the paragraph below."""
    body = """{
  ariaLabel: "Merged by team",
  color: {legend: true},
  marks: [Plot.barY(Array.from({length: 14}, (_, n) => ({team: `team ${n + 1}`, n})),
                    {x: "team", y: "n", fill: "team"})],
}"""
    source = leaf_page(
        "legend chart",
        '<h1 id="t">Merged</h1>\n'
        + chart_markup("c-legend", body).replace(
            '<lf-chart id="c-legend">', '<lf-chart id="c-legend" data-height="300">'
        )
        + "<p>After the chart.</p>",
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    measured = """() => {
        const el = document.getElementById('c-legend');
        const svg = el.querySelector('svg[role=img]').getBoundingClientRect();
        const legend = el.querySelector('div[class*="-swatches"]').getBoundingClientRect();
        return {legend: legend.height, overhang: svg.bottom - el.getBoundingClientRect().bottom};
    }"""
    before = page.evaluate(measured)
    assert abs(before["overhang"]) <= 0.5, before
    page.locator("#c-legend").evaluate("el => el.style.letterSpacing = '0.5em'")
    page.wait_for_function(
        f"(before) => ({measured})().legend > before + 4", arg=before["legend"]
    )
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() =>"
        " requestAnimationFrame(done)))"
    )
    after = page.evaluate(measured)
    assert abs(after["overhang"]) <= 0.5, (before, after)


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


# A chart's values, which a chart says to the pointer, the keyboard and a finger
# (lf-chart.js, chart-points.js). Two series stacked in two weeks, so a step runs along
# a series and across to the other, and a stack's share is what a segment measures.
HOURS = chart_markup(
    "hours",
    """{
  ariaLabel: "Hours by week: features 21 and 18, fixes 9 and 14",
  y: {label: "hours"},
  color: {range: ["var(--series-1)", "var(--series-2)"]},
  marks: [
    Plot.barY(
      [
        {week: "w1", kind: "features", hours: 21},
        {week: "w2", kind: "features", hours: 18},
        {week: "w1", kind: "fixes", hours: 9},
        {week: "w2", kind: "fixes", hours: 14},
      ],
      {x: "week", y: "hours", fill: "kind"},
    ),
  ],
}""",
)
VALUES_PAGE = leaf_page(
    "chart values", f'<h1 id="t">Hours</h1><button id="before">Before</button>{HOURS}'
)


def said(page):
    """What the preview says, its name line and its detail lines, or None while it is
    put away."""
    preview = page.locator(PREVIEW)
    if not preview.evaluate("tip => tip.matches(':popover-open')"):
        return None
    return [
        preview.locator(".lf-preview-word").inner_text(),
        *preview.locator(".lf-preview-detail").all_inner_texts(),
    ]


def column(page, chart, week, height=0.15):
    """A point over `week`'s column of `chart`, `height` of the way down its drawing."""
    ticks = page.locator(f"#{chart} [data-lf-part='x-axis tick label'] text")
    box = ticks.get_by_text(week, exact=True).bounding_box()
    drawing = page.locator(f"#{chart} svg[role=img]").bounding_box()
    return box["x"] + box["width"] / 2, drawing["y"] + drawing["height"] * height


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_chart_says_the_value_under_the_pointer_and_the_keyboard(
    engine, request, serve
):
    """A resting pointer reads the point nearest it, standing above the ring on that
    point, and moving along the drawing reads each point it comes to at once; leaving
    the drawing puts both away, and so does leaving the window from the preview. After
    Escape puts them away, the pointer reads nothing on that point and reads the next
    point it reaches. Focus
    the browser shows lands on the first point, the arrows step along a series and
    across to the other, and Home and End reach a series' ends. Escape puts the preview
    and the ring away, a redraw brings back neither, and an arrow steps on from where
    Escape left it and shows both again. With the preview put away, Escape leaves the
    chart. Each line the preview says is one of Plot's rows."""
    page = open_page(request.getfixturevalue(engine), serve(VALUES_PAGE))
    chart = page.locator("#hours")
    preview = page.locator(PREVIEW)
    ring = chart.locator(".lf-chart-at circle")
    expect(chart.locator("svg[role=img]")).to_be_visible()

    page.mouse.move(*column(page, "hours", "w2", 0.2))
    page.mouse.move(*column(page, "hours", "w2", 0.15))
    expect(preview).to_be_visible()
    assert said(page) == ["week w2", "kind fixes", "hours 14"]
    expect(preview).to_have_attribute("data-lf-route", "pointer")
    tip, at = preview.bounding_box(), ring.bounding_box()
    assert tip["y"] + tip["height"] <= at["y"], (tip, at)
    # The pointer may cross onto the preview to read it, which keeps the point.
    page.mouse.move(tip["x"] + tip["width"] / 2, tip["y"] + tip["height"] / 2)
    page.wait_for_timeout(300)
    assert said(page) == ["week w2", "kind fixes", "hours 14"]
    expect(ring).to_be_visible()
    page.mouse.move(*column(page, "hours", "w1", 0.85))
    expect(preview.locator(".lf-preview-detail")).to_have_text(
        ["kind features", "hours 21"]
    )
    # Redrawn where it stands, never put away between the points.
    assert said(page) == ["week w1", "kind features", "hours 21"]
    # Escape puts the preview and the ring away; the pointer still on that point reads
    # nothing, and the next point it reaches reads at once.
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    expect(ring).to_be_hidden()
    page.mouse.move(*column(page, "hours", "w1", 0.8))
    page.wait_for_timeout(300)
    expect(preview).to_be_hidden()
    page.mouse.move(*column(page, "hours", "w2", 0.15))
    expect(preview.locator(".lf-preview-detail")).to_have_text(
        ["kind fixes", "hours 14"]
    )
    expect(ring).to_be_visible()
    page.mouse.move(2, 2)
    expect(preview).to_be_hidden()
    expect(ring).to_be_hidden()

    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(chart).to_be_focused()
    expect(preview).to_have_attribute("data-lf-route", "focus")
    assert said(page) == ["week w1", "kind features", "hours 21"]
    for key, words in (
        ("ArrowRight", ["week w2", "kind features", "hours 18"]),
        ("ArrowDown", ["week w2", "kind fixes", "hours 14"]),
        ("Home", ["week w1", "kind fixes", "hours 9"]),
        ("ArrowUp", ["week w1", "kind features", "hours 21"]),
        ("End", ["week w2", "kind features", "hours 18"]),
    ):
        page.keyboard.press(key)
        expect(preview.locator(".lf-preview-detail")).to_have_text(words[1:])
        assert said(page) == words, key

    # Focus arriving on a point the pointer reads takes it over: the pointer leaving
    # leaves it, and the arrows step on from it.
    page.keyboard.press("Shift+Tab")
    expect(preview).to_be_hidden()
    page.mouse.move(*column(page, "hours", "w2", 0.2))
    page.mouse.move(*column(page, "hours", "w2", 0.15))
    expect(preview.locator(".lf-preview-detail")).to_have_text(
        ["kind fixes", "hours 14"]
    )
    page.keyboard.press("Tab")
    expect(chart).to_be_focused()
    page.mouse.move(2, 2)
    expect(preview).to_have_attribute("data-lf-route", "focus")
    assert said(page) == ["week w2", "kind fixes", "hours 14"]
    page.keyboard.press("ArrowLeft")
    expect(preview.locator(".lf-preview-detail")).to_have_text(
        ["kind fixes", "hours 9"]
    )
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    expect(ring).to_be_hidden()
    expect(chart).to_be_focused()
    # A redraw for a new width brings back neither.
    drawn = chart.evaluate("el => el.drawn")
    chart.evaluate("el => { el.style.width = `${el.clientWidth - 80}px`; }")
    page.wait_for_function(
        "([drawn]) => document.getElementById('hours').drawn !== drawn", arg=[drawn]
    )
    page.wait_for_timeout(300)
    expect(preview).to_be_hidden()
    expect(ring).to_be_hidden()
    # A key's step is the user aiming again: it steps on from the point Escape put
    # away and shows the preview again.
    page.keyboard.press("ArrowRight")
    expect(preview).to_be_visible()
    expect(ring).to_be_visible()
    assert said(page) == ["week w2", "kind fixes", "hours 14"]
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    page.keyboard.press("Escape")
    expect(chart).not_to_be_focused()

    # Leaving the window from the preview puts it away, and its point with it.
    page.mouse.move(*column(page, "hours", "w2", 0.2))
    page.mouse.move(*column(page, "hours", "w2", 0.15))
    expect(preview).to_be_visible()
    tip = preview.bounding_box()
    page.mouse.move(tip["x"] + tip["width"] / 2, tip["y"] + tip["height"] / 2)
    preview.evaluate(
        "tip => tip.dispatchEvent(new PointerEvent('pointerout',"
        " {bubbles: true, pointerType: 'mouse', relatedTarget: null}))"
    )
    expect(preview).to_be_hidden()
    expect(ring).to_be_hidden()
    assert chart.evaluate("el => el.lfPreview()") is None
    page.mouse.move(2, 2)


def test_a_finger_held_on_a_chart_reads_the_point_under_it(browser, serve):
    """A finger held on the drawing reads the point under it at the platform's long
    press, above the finger, and reads each point it slides across to. Lifting presses
    nothing and leaves the preview and its ring standing, until the next touch puts
    them away. Chromium alone: Playwright holds no finger in Firefox."""
    context = browser.new_context(has_touch=True)
    page = open_page(browser, serve(VALUES_PAGE), context=context)
    preview = page.locator(PREVIEW)
    ring = page.locator("#hours .lf-chart-at circle")
    expect(page.locator("#hours svg[role=img]")).to_be_visible()
    cdp = context.new_cdp_session(page)

    def touch(kind, at=None):
        points = [{"x": at[0], "y": at[1]}] if at else []
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})

    start = column(page, "hours", "w2")
    touch("touchStart", start)
    page.wait_for_timeout(600)
    expect(preview).to_be_hidden()
    assert long_press(page, {"x": start[0], "y": start[1]}) is False
    expect(preview).to_be_visible()
    expect(preview).to_have_attribute("data-lf-route", "hold")
    assert said(page) == ["week w2", "kind fixes", "hours 14"]
    assert preview.bounding_box()["y"] < start[1]
    # The slide crosses the gap between the columns, where no point is near enough to
    # read, so the preview goes and comes back on the next column.
    end = column(page, "hours", "w1")
    for step in range(1, 7):
        touch("touchMove", (start[0] + (end[0] - start[0]) * step / 6, start[1]))
    expect(preview).to_be_visible()
    assert said(page) == ["week w1", "kind fixes", "hours 9"]
    touch("touchEnd")
    render_checks_model.rendered(page)
    expect(preview).to_be_visible()
    assert said(page) == ["week w1", "kind fixes", "hours 9"]
    expect(ring).to_be_visible()
    heading = page.locator("#t").bounding_box()
    touch("touchStart", (heading["x"] + 10, heading["y"] + heading["height"] / 2))
    touch("touchEnd")
    expect(preview).to_be_hidden()
    expect(ring).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_chart_s_preview_keeps_its_side_from_point_to_point(engine, request, serve):
    """A pointer sweeping a chart at the window's top reads each point with the preview
    on one side of it, never over it: above while there is room, and below from the
    first point too high for that, staying there for the points after."""
    swings = chart_markup(
        "swings",
        """{
  ariaLabel: "A value rising and falling over twelve steps",
  marks: [Plot.lineY(
    Array.from({length: 12}, (_, n) => ({step: n, value: n % 3 ? 80 - n * 3 : 5})),
    {x: "step", y: "value", marker: "dot"},
  )],
}""",
    ).replace('<lf-chart id="swings">', '<lf-chart id="swings" data-height="320">')
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "swings",
                f'<h1 id="t">Swings</h1>{swings}<p style="height: 1200px">After.</p>',
            )
        ),
    )
    chart = page.locator("#swings")
    expect(chart.locator("svg[role=img]")).to_be_visible()
    chart.evaluate("el => { el.scrollIntoView({block: 'start'}); scrollBy(0, -6); }")
    drawing = chart.locator("svg[role=img]").bounding_box()
    sides = []
    for k in range(48):
        x = drawing["x"] + drawing["width"] * (0.04 + 0.92 * k / 47)
        page.mouse.move(x, drawing["y"] + drawing["height"] / 2)
        page.wait_for_timeout(250 if k == 0 else 30)
        side = page.evaluate(
            """() => {
              const tip = document.getElementById('lf-preview');
              const ring = document.querySelector('#swings .lf-chart-at circle');
              if (!tip.matches(':popover-open') || !ring) return null;
              const t = tip.getBoundingClientRect(), r = ring.getBoundingClientRect();
              return t.bottom <= r.top + 0.5 ? 'above' : t.top >= r.bottom - 0.5
                ? 'below' : 'over';
            }"""
        )
        if side and (not sides or sides[-1] != side):
            sides.append(side)
    assert sides in (["above"], ["above", "below"], ["below"]), sides


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_chart_s_author_picks_which_marks_say_their_values_and_their_words(
    engine, request, serve
):
    """Where an author gives some marks Plot's `tip`, only those say their values, and
    a mark's `title` channel says its own words, its first line as the name and the rest
    beneath, with no platform tooltip beside them."""
    picked = chart_markup(
        "picked",
        """{
  ariaLabel: "Hours by week: 21, 18 and 30, the third the release",
  marks: [
    Plot.lineY(
      [{week: "w1", hours: 21}, {week: "w2", hours: 18}, {week: "w3", hours: 30}],
      {x: "week", y: "hours"},
    ),
    Plot.dot([{week: "w3", hours: 30}], {
      x: "week",
      y: "hours",
      tip: true,
      title: (d) => `Release ${d.week}\\nshipped on time`,
    }),
  ],
}""",
    )
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("picked", f'<h1 id="t">Hours</h1>{picked}')),
    )
    preview = page.locator(PREVIEW)
    expect(page.locator("#picked svg[role=img]")).to_be_visible()
    expect(page.locator("#picked title")).to_have_count(0)
    # `tip: true` is Plot's nearest point in both axes, so the pointer comes to the dot.
    dot = page.locator("#picked [data-lf-part=dot] circle").bounding_box()
    page.mouse.move(dot["x"] + 12, dot["y"] + 12)
    page.mouse.move(dot["x"] + dot["width"] / 2, dot["y"] + dot["height"] / 2)
    expect(preview).to_be_visible()
    assert said(page) == ["Release w3", "shipped on time"]
    page.mouse.move(*column(page, "picked", "w1", 0.25))
    expect(preview).to_be_hidden()
    expect(page.locator("#picked .lf-chart-at")).to_be_hidden()


# Each chart drawn twice, by lf-chart and by Plot alone with Plot's tip on each mark set
# to read as lf-chart reads it: the axis the author named or the mark's points stand
# along, and the mark's frame anchor, which Plot's own tip leaves at the frame's middle.
# Each datum's title names it, so the chart's reading and Plot's `input` name one datum.
FACETED_ROWS = (
    "[0, 2, 4, 6, 8].map((x) => ({id: `a${x}`, k: 'a', x, y: x % 4}))"
    ".concat([1, 3, 5, 7, 9].map((x) => ({id: `b${x}`, k: 'b', x: x + 0.1, y: 9 - x})))"
)
LINE_ROWS = "[0, 1, 2, 3, 4, 5].map((x) => ({id: `l${x}`, x, y: (x * 7) % 5}))"
DOT_ROWS = "[0.5, 2.5, 4.5].map((x) => ({id: `d${x}`, x, y: x}))"
ANCHORED_ROWS = "[1, 2, 4, 7].map((x) => ({id: `n${x}`, x}))"
BAR_ROWS = "[3, 9, 4, 12, 7].map((v, i) => ({id: `b${i}`, i, v}))"
TWICE_ROWS = "[1, 4, 6, 9].map((x) => ({id: `t${x}`, x, y: (x * 3) % 10}))"
PICK_ROWS = '[{id: "left", x: 2, y: 5, pickX: 8}, {id: "right", x: 8, y: 5, pickX: 2}]'
SHARE_ROWS = (
    '[{id: "low", x: 0.2, y: 1, pick: 0.8}, {id: "high", x: 0.8, y: 2, pick: 0.2}]'
)
# Stacks of different heights, so that no aim below stands near halfway between two
# segments' middles.
STACK_ROWS = (
    '["a", "b", "c"].flatMap((k, n) => [{id: `${k}1`, k, s: "one", v: 2 + 2 * n},'
    ' {id: `${k}2`, k, s: "two", v: 6 - n}])'
)
LINKED_ROWS = (
    '[{x: 2, y: 3, c: "red", u: "https://a.example/one"},'
    ' {x: 7, y: 8, c: "blue", u: "https://a.example/two"}]'
)
POINTER_CASES = {
    "faceted": (
        f'Plot.dot({FACETED_ROWS}, {{x: "x", y: "y", fy: "k", title: "id", tip: "x"}})',
        f'Plot.dot({FACETED_ROWS}, {{x: "x", y: "y", fy: "k", title: "id", tip: "x"}})',
    ),
    "anchored": (
        f'Plot.dotX({ANCHORED_ROWS}, {{x: "x", frameAnchor: "bottom", title: "id"}})',
        f'Plot.dotX({ANCHORED_ROWS}, {{x: "x", frameAnchor: "bottom", title: "id",'
        ' tip: {frameAnchor: "bottom"}})',
    ),
    "along-y": (
        'Plot.dot([{id: "low", x: 0, y: 0}, {id: "high", x: 10, y: 10}],'
        ' {x: "x", y: "y", title: "id", tip: "y"})',
        'Plot.dot([{id: "low", x: 0, y: 0}, {id: "high", x: 10, y: 10}],'
        ' {x: "x", y: "y", title: "id", tip: "y"})',
    ),
    "bars": (
        f'Plot.barY({BAR_ROWS}, {{x: "i", y: "v", title: "id"}})',
        f'Plot.barY({BAR_ROWS}, {{x: "i", y: "v", title: "id", tip: "x"}})',
    ),
    # Two marks, each of whose tips Plot shows: the chart reads the nearer.
    "two-marks": (
        f'Plot.lineY({LINE_ROWS}, {{x: "x", y: "y", title: "id", tip: "x"}}),'
        f' Plot.dot({DOT_ROWS}, {{x: "x", y: "y", title: "id", tip: "xy"}})',
        f'Plot.lineY({LINE_ROWS}, {{x: "x", y: "y", title: "id", tip: "x"}}),'
        f' Plot.dot({DOT_ROWS}, {{x: "x", y: "y", title: "id", tip: "xy"}})',
    ),
    # One data drawn twice, each mark picking by its own tip: along x where the first
    # reads both axes, and within a reach the first's doesn't have, one no aim below
    # comes within 3px of, since the two drawings stand at different fractions of a
    # pixel.
    **{
        name: (marks, marks)
        for name, marks in {
            "twice-along": (
                f'Plot.dot({TWICE_ROWS}, {{x: "x", y: "y", title: "id", tip: true}}),'
                f' Plot.dot({TWICE_ROWS}, {{x: "x", y: "y", title: "id", tip: "x"}})'
            ),
            "twice-reach": (
                f'Plot.dot({TWICE_ROWS}, {{x: "x", y: "y", title: "id",'
                " tip: {maxRadius: 1}}),"
                f' Plot.dot({TWICE_ROWS}, {{x: "x", y: "y", title: "id",'
                " tip: {maxRadius: 75}})"
            ),
            # Picked by values of its own, wherever each datum stands, on a scale
            # that transforms them as it does the data.
            "picked": (
                f'Plot.dot({PICK_ROWS}, {{x: "x", y: "y", title: "id",'
                ' tip: {px: "pickX"}})'
            ),
            "picked-share": (
                f'Plot.dot({SHARE_ROWS}, {{x: "x", y: "y", title: "id",'
                ' tip: {px: "pick"}})'
            ),
            # Stacked segments, each read at the middle of its extent.
            "stacked": (
                f'Plot.barY({STACK_ROWS}, {{x: "k", y: "v", fill: "s", title: "id",'
                ' tip: "x"})'
            ),
            # Words chosen by the tip's format: a colour written as a colour and a
            # link, which Plot's tip leaves out unless named, and a channel left out.
            "formatted": (
                f'Plot.dot({LINKED_ROWS}, {{x: "x", y: "y", fill: "c", href: "u",'
                ' tip: {format: {fill: true, href: true, y: ".1f", x: false}}})'
            ),
            # Two channels under one label, which Plot's tip says once.
            "one-label": (
                "Plot.dot([{a: 1, b: 2}, {a: 6, b: 8}],"
                ' {x: "a", y: "b", fill: "a", tip: true})'
            ),
            # A format that gives a value nothing, which Plot's tip leaves at its label.
            "blank-value": (
                "Plot.dot([{x: 1, y: 2}, {x: 6, y: 8}],"
                ' {x: "x", y: "y", tip: {format: {y: () => null}}})'
            ),
            # Two rows whose values read the same, each still its own line.
            "same-values": (
                'Plot.dot([{district: "A", team: "A", sales: 2},'
                ' {district: "B", team: "C", sales: 5}],'
                ' {x: "district", y: "sales", fill: "team", tip: true})'
            ),
        }.items()
    },
}
# Scale options a case's chart and Plot's beside it are drawn with.
CASE_SCALES = {"picked-share": "x: {percent: true, domain: [0, 100]}, "}
# A mark moved by its offsets, which Plot's pointer leaves out: the chart reads the
# datum Plot draws under the pointer.
MOVED = (
    'Plot.dot([{id: "p", x: 2, y: 2}, {id: "q", x: 5, y: 3}, {id: "r", x: 7, y: 6}],'
    ' {x: "x", y: "y", dx: 40, dy: -24, r: 6, title: "id"})'
)
POINTER_PAGE = leaf_page(
    "pointer cases",
    '<h1 id="t">Pointer cases</h1>'
    + "".join(
        chart_markup(
            name,
            f'{{ariaLabel: "{name}", x: {{domain: [0, 10]}}, y: {{domain: [0, 10]}},'
            f" marks: [{marks}]}}"
            if name == "moved"
            else f'{{ariaLabel: "{name}", {CASE_SCALES.get(name, "")}marks: [{marks}]}}',
        ).replace("<lf-chart ", '<lf-chart data-height="200" ')
        for name, marks in [
            *((name, ours) for name, (ours, _) in POINTER_CASES.items()),
            ("moved", MOVED),
        ]
    ),
)
# What a drawing shows picked, in the svg's coordinates: lf-chart's ring and the lines
# its preview says, or each tip Plot's own pointer shows, where it points from and the
# row each of its lines says: the label Plot sets in bold, and the value after it, the
# whole value where Plot cuts a line short, less the zero-width space it starts each
# line with.
PICKED = """(svg) => {
    const box = svg.getBoundingClientRect();
    const where = (node) => {
      const at = node.getScreenCTM();
      return [at.e - box.left, at.f - box.top];
    };
    const ring = svg.querySelector('.lf-chart-at:not([display=none])');
    const chart = svg.closest('lf-chart');
    if (chart) {
      const said = chart.lfPreview();
      return ring ? [{at: where(ring), lines: [said?.name ?? '', ...(said?.detail ?? [])]}] : [];
    }
    const clean = (text) => text.replaceAll('\\u200b', '').trim();
    return [...svg.querySelectorAll('[aria-label=tip] path')].map((path) => ({
      at: where(path.parentElement),
      rows: [...path.parentElement.querySelectorAll('text > tspan')].map((line) => [
        clean(line.querySelector('tspan[font-weight=bold]')?.textContent ?? ''),
        clean(line.querySelector('title')?.textContent ??
          [...line.childNodes].filter((node) => node.nodeType === 3)
            .map((node) => node.textContent).join('')),
      ]),
    }));
}"""


def _says_plot_s_rows(lines, rows):
    """Whether a reading's lines are Plot's rows, one line for each, as Plot's tip
    draws it: its label, then its value, either alone where the other is empty. A line
    pairing a value with another row's label, a row left unsaid, or a line Plot has no
    row for, fails."""
    unsaid = list(lines)
    for row in rows:
        line = " ".join(part for part in row if part)
        if line not in unsaid:
            return False
        unsaid.remove(line)
    return not unsaid


def _picked(page, svg, box, fx, fy):
    page.mouse.move(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() =>"
        " requestAnimationFrame(done)))"
    )
    return page.locator(svg).evaluate(PICKED)


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
    dots = moved.locator("[data-lf-part=dot] circle").all()
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
