"""An authored timeline steps through its events by every route, lays its labels out
clear of one another at any width, and prints whole. The step is tab-local view
state."""

from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, select, told

from leaf.render_checks import wait_until_ready

RACE = """<h1>Race</h1>
<lf-timeline id="race" aria-label="The race">
  <lf-lane label="Job A">
    <lf-event id="a-read" at="0" label="Reads balance: 100"></lf-event>
    <lf-event id="a-work" at="200" end="4200" label="Adds 50"></lf-event>
    <lf-event id="a-write" at="4200" label="Writes 150"></lf-event>
  </lf-lane>
  <lf-lane label="Job B">
    <lf-event id="b-read" at="1000" label="Reads balance: 100"></lf-event>
    <lf-event id="b-work" at="1200" end="5200" label="Subtracts 30 from the stale 100"></lf-event>
    <lf-event id="b-write" at="5200" label="Writes 70"></lf-event>
  </lf-lane>
  <lf-lane label="Balance">
    <lf-event id="balance-start" at="0" label="100"></lf-event>
    <lf-event id="balance-a" at="4200" label="150"></lf-event>
    <lf-event id="balance-b" at="5200" label="70: A's deposit is lost"></lf-event>
  </lf-lane>
</lf-timeline>"""

# Each lane's label boxes, and the chart's track, in viewport pixels.
LABEL_BOXES = """() => {
  const track = document.querySelector('#race').querySelector('.lf-timeline-ruler').getBoundingClientRect();
  const lanes = [...document.querySelector('#race').querySelectorAll('.lf-timeline-lane')].map((lane) =>
    [...lane.querySelectorAll('.lf-timeline-label')].map((label) => {
      const box = label.getBoundingClientRect();
      return { left: box.left, right: box.right, top: box.top, clipped: label.scrollWidth > label.clientWidth };
    }),
  );
  return { left: track.left, right: track.right, lanes };
}"""


NEXT_FRAME = "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"


def assert_labels_clear(page):
    reading = page.evaluate(LABEL_BOXES)
    for lane in reading["lanes"]:
        for label in lane:
            assert not label["clipped"], label
            assert reading["left"] - 0.5 <= label["left"], (label, reading["left"])
            assert label["right"] <= reading["right"] + 0.5, (label, reading["right"])
        for index, one in enumerate(lane):
            for other in lane[index + 1 :]:
                if abs(one["top"] - other["top"]) < 1:
                    assert (
                        one["right"] <= other["left"] or other["right"] <= one["left"]
                    ), (
                        one,
                        other,
                    )


def test_timeline_steps_by_every_route_and_keeps_the_step(browser, serve):
    page = open_page(browser, serve(leaf_page("Race", RACE), packages=("timeline",)))
    position = page.locator("#race .lf-timeline-position")
    rows = page.locator("#race .lf-timeline-step")
    expect(position).to_have_text("Step 1 of 6 · 0 s")
    # Events that start together share a step, and a span's end is no step.
    expect(rows).to_have_count(6)
    expect(rows.nth(0)).to_have_attribute("aria-current", "step")

    # The position's words change width with each step, so they follow both buttons
    # and never move the one being pressed.
    next_button = page.get_by_role("button", name="Next")
    before = next_button.bounding_box()
    next_button.click()
    expect(position).to_have_text("Step 2 of 6 · 0.2 s")
    assert next_button.bounding_box() == before
    page.keyboard.press("ArrowRight")
    expect(position).to_have_text("Step 3 of 6 · 1 s")
    # A key's step is said aloud, which Leaf does for the timeline (`announce`).
    expect(page.locator(".lf-live")).to_have_text(
        "Step 3 of 6. Job B: Reads balance: 100"
    )
    page.keyboard.press("End")
    expect(position).to_have_text("Step 6 of 6 · 5.2 s")
    expect(page.get_by_role("button", name="Next")).to_have_attribute(
        "aria-disabled", "true"
    )

    # Taking a passage from another step keeps the playhead where it was.
    words = rows.nth(1).locator(".lf-timeline-step-event").first
    box = words.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 1, y), (box["x"] + box["width"] - 1, y))
    assert "Adds 50" in page.evaluate("getSelection().toString()")
    expect(position).to_have_text("Step 6 of 6 · 5.2 s")
    page.keyboard.press("Enter")
    expect(position).to_have_text("Step 2 of 6 · 0.2 s")
    # Tab reaches the next row; Space takes the playhead there.
    page.keyboard.press("Tab")
    page.keyboard.press("Space")
    expect(position).to_have_text("Step 3 of 6 · 1 s")

    # A row of the step list, and a press on a mark, go to that event's step.
    rows.nth(3).click()
    expect(position).to_have_text("Step 4 of 6 · 1.2 s")
    page.locator('[data-event="a-write"] .lf-timeline-mark').click()
    expect(position).to_have_text("Step 5 of 6 · 4.2 s")

    # From a row, the arrows carry focus along the list with the step.
    rows.nth(1).click()
    page.keyboard.press("ArrowRight")
    expect(rows.nth(2)).to_be_focused()
    expect(rows.nth(2)).to_have_attribute("aria-current", "step")

    page.reload()
    wait_until_ready(page)
    expect(position).to_have_text("Step 3 of 6 · 1 s")


def test_timeline_labels_stay_clear_at_any_width_and_on_paper(browser, serve):
    page = open_page(browser, serve(leaf_page("Race", RACE), packages=("timeline",)))
    assert_labels_clear(page)
    # The ruler picks round intervals, and events with room share a label row.
    expect(page.locator("#race .lf-timeline-tick[data-major]")).to_have_text(
        ["0 s", "1 s", "2 s", "3 s", "4 s", "5 s"]
    )
    lanes = page.evaluate(LABEL_BOXES)["lanes"]
    assert any(len({label["top"] for label in lane}) < len(lane) for lane in lanes)
    chart = page.locator("#race .lf-timeline-chart")
    before = chart.bounding_box()
    page.get_by_role("button", name="Next").click()
    assert chart.bounding_box() == before
    assert_labels_clear(page)

    # A narrower window lays the labels out again before the next frame paints.
    page.set_viewport_size({"width": 390, "height": 900})
    page.evaluate(NEXT_FRAME)
    assert_labels_clear(page)

    page.set_viewport_size({"width": 1280, "height": 900})
    page.emulate_media(media="print")
    # Paper drops controls, but keeps the chart, laid out again at its width, and the
    # step list as text.
    expect(page.locator("#race .lf-timeline-chart")).to_be_visible()
    expect(page.locator("#race .lf-timeline-step").first).to_be_visible()
    expect(page.get_by_role("button", name="Next")).to_be_hidden()
    page.set_viewport_size({"width": 700, "height": 900})
    page.evaluate(NEXT_FRAME)
    assert_labels_clear(page)


def test_timeline_revision_keeps_position_and_updates_labels_steps_and_routes(
    browser, serve
):
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Race",
                    "<details open><summary>Sequence</summary>" + RACE + "</details>",
                ),
                packages=("timeline",),
            )
        ),
    )
    page.get_by_role("button", name="Next", exact=True).click()
    source = serve.page_dir / "index.html"
    before = page.locator("#race .lf-timeline-next").bounding_box()
    source.write_text(source.read_text().replace('label="Adds 50"', 'label="Adds 75"'))
    told(page)
    expect(page.locator('#race [data-event="a-work"] .lf-timeline-label')).to_have_text(
        "Adds 75"
    )
    assert page.locator("#race .lf-timeline-next").bounding_box() == before
    page.get_by_text("Sequence", exact=True).click()
    source.write_text(
        source.read_text()
        .replace(
            '<lf-event id="a-write"',
            '<lf-event id="a-check" at="300" label="Checks the amount"></lf-event><lf-event id="a-write"',
        )
        .replace(
            "</main>",
            '<lf-timeline id="arriving" aria-label="Arriving timeline"><lf-lane label="Arrival"><lf-event id="arriving-event" at="0" label="Arrives in revision"></lf-event></lf-lane></lf-timeline></main>',
        )
    )
    told(page)
    page.get_by_text("Sequence", exact=True).click()
    race = page.locator("#race")
    expect(race.locator(".lf-timeline-step")).to_have_count(7)
    expect(race.locator(".lf-timeline-position")).to_have_text("Step 2 of 7 · 0.2 s")
    expect(race.locator('[data-event="a-work"] .lf-timeline-label')).to_have_text(
        "Adds 75"
    )
    added = race.locator(".lf-timeline-step").filter(has_text="Checks the amount")
    added.focus()
    added.press("Enter")
    expect(race.locator(".lf-timeline-position")).to_have_text("Step 3 of 7 · 0.3 s")
    added.press("End")
    expect(race.locator(".lf-timeline-position")).to_have_text("Step 7 of 7 · 5.2 s")
    expect(page.locator("#arriving .lf-timeline-position")).to_have_text(
        "Step 1 of 1 · 0 s"
    )


def test_a_timeline_s_unavailable_arrow_reaches_no_command_around_it(browser, serve):
    """Next at the last step is unavailable, and its arrow stays the timeline's: a deck
    around it keeps its card."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Deck with a timeline",
                """<h1>Deck with a timeline</h1>
<lf-deck id="deck">
  <section id="card-one">
    <h2>First card</h2>
    <lf-timeline id="tl" aria-label="Two steps">
      <lf-lane label="Build">
        <lf-event id="e1" at="0" label="Compile"></lf-event>
        <lf-event id="e2" at="1000" label="Ship"></lf-event>
      </lf-lane>
    </lf-timeline>
  </section>
  <section id="card-two"><h2>Second card</h2><p>The deck moved on.</p></section>
</lf-deck>""",
            ),
            packages=("timeline", "deck"),
        ),
    )
    rows = page.locator("#tl .lf-timeline-step")
    rows.last.click()
    expect(rows.last).to_have_attribute("aria-current", "step")
    expect(page.locator("#tl .lf-timeline-next")).to_have_attribute(
        "aria-disabled", "true"
    )
    page.keyboard.press("ArrowRight")
    expect(rows.last).to_be_focused()
    page.evaluate(NEXT_FRAME)
    assert page.evaluate(
        """() => [...document.querySelectorAll('#deck > section')]
          .filter((card) => card.hasAttribute('data-lf-deck-open')).map((card) => card.id)"""
    ) == ["card-one"]
