"""An authored timeline steps through its events by every route, lays its labels out
clear of one another at any width, and prints whole. The step is tab-local view
state."""

from playwright.sync_api import expect
from render_harness import leaf_page, open_page, select

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
  const track = document.querySelector('#race .lf-timeline-ruler').getBoundingClientRect();
  const lanes = [...document.querySelectorAll('#race .lf-timeline-lane')].map((lane) =>
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
