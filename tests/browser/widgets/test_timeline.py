"""An authored timeline steps through its events by every route, lays its labels out
clear of one another at any width with each label's stroke at its event's moment, and
prints whole. The step is tab-local view state."""

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

# Two labels too long to read either way from their mark in a phone's column, and
# whole in a desktop's.
HANDOVER = """<h1>Handover</h1>
<lf-timeline id="handover" aria-label="A handover">
  <lf-lane label="Leaf">
    <lf-event id="hold" at="0" end="12600" label="Holds your question back"></lf-event>
    <lf-event id="post" at="12600" label="Posts the fork's answer"></lf-event>
    <lf-event id="carry" at="25000" label="Hook hands over the exchange"></lf-event>
  </lf-lane>
  <lf-lane label="Session">
    <lf-event id="command" at="0" end="25000"
      label="Runs the command your question waits behind, start to finish"></lf-event>
    <lf-event id="reply" at="45900" label="Reply posted"></lf-event>
  </lf-lane>
</lf-timeline>"""

# Each lane's labels, and the chart's track, in viewport pixels. A label's stroke is
# whichever inline border it draws; its event's moment is an instant mark's centre
# or a span mark's start.
LABEL_BOXES = """(timeline) => {
  const host = document.querySelector(timeline);
  const track = host.querySelector('.lf-timeline-ruler').getBoundingClientRect();
  const lanes = [...host.querySelectorAll('.lf-timeline-lane')].map((lane) =>
    [...lane.querySelectorAll('.lf-timeline-event')].map((event) => {
      const label = event.querySelector('.lf-timeline-label');
      const mark = event.querySelector('.lf-timeline-mark');
      const box = label.getBoundingClientRect();
      const markBox = mark.getBoundingClientRect();
      const style = getComputedStyle(label);
      return {
        id: event.dataset.lfEvent,
        left: box.left,
        right: box.right,
        top: box.top,
        stroke: parseFloat(style.borderLeftWidth) ? box.left : parseFloat(style.borderRightWidth) ? box.right : null,
        moment: mark.dataset.lfKind === 'instant' ? (markBox.left + markBox.right) / 2 : markBox.left,
        // The label's words at full length, with its padding and stroke.
        whole: label.scrollWidth + box.width - label.clientWidth,
        clipped: label.scrollWidth > label.clientWidth,
      };
    }),
  );
  return { left: track.left, right: track.right, lanes };
}"""


NEXT_FRAME = "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"


def assert_labels_clear(page, timeline="#race"):
    """Every label stands inside the track and clear of the others in its row, its
    stroke at its event's moment, and whole unless neither side of its mark has room
    for all its words. Returns each label's reading by event id."""
    reading = page.evaluate(LABEL_BOXES, timeline)
    for lane in reading["lanes"]:
        for label in lane:
            assert label["stroke"] is not None, label
            assert abs(label["stroke"] - label["moment"]) < 1, label
            room = max(
                label["moment"] - reading["left"], reading["right"] - label["moment"]
            )
            assert not label["clipped"] or label["whole"] > room, (label, room)
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
    return {label["id"]: label for lane in reading["lanes"] for label in lane}


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
    rows.nth(1).evaluate(
        "row => { window.pressed = 0; row.addEventListener('click', () => pressed++); }"
    )
    page.keyboard.press("Enter")
    expect(position).to_have_text("Step 2 of 6 · 0.2 s")
    # The row is a span pressed as a button is, and nothing of Leaf's presses it again.
    assert page.evaluate("pressed") == 1
    # Tab reaches the next row; Space takes the playhead there.
    page.keyboard.press("Tab")
    page.keyboard.press("Space")
    expect(position).to_have_text("Step 3 of 6 · 1 s")

    # A row of the step list, and a press on a mark, go to that event's step.
    rows.nth(3).click()
    expect(position).to_have_text("Step 4 of 6 · 1.2 s")
    page.locator('[data-lf-event="a-write"] .lf-timeline-mark').click()
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
    expect(page.locator("#race .lf-axis-tick[data-lf-major]")).to_have_text(
        ["0 s", "1 s", "2 s", "3 s", "4 s", "5 s"]
    )
    lanes = page.evaluate(LABEL_BOXES, "#race")["lanes"]
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


def test_a_label_with_no_room_beside_its_mark_keeps_its_stroke_there(browser, serve):
    """A label too long to read either way from its mark ends its words at the
    track's edge, its stroke still at its event's moment, rather than move clear of
    the mark and leave its stroke at a time the event isn't."""
    page = open_page(
        browser, serve(leaf_page("Handover", HANDOVER), packages=("timeline",))
    )
    crowded = ("carry", "command")
    labels = assert_labels_clear(page, "#handover")
    assert not any(labels[event]["clipped"] for event in crowded), labels
    # One reads on from its mark, the other back from it, as each has more room.
    page.set_viewport_size({"width": 390, "height": 900})
    page.evaluate(NEXT_FRAME)
    labels = assert_labels_clear(page, "#handover")
    assert all(labels[event]["clipped"] for event in crowded), labels


RUNS = """<h1>Race</h1>
<lf-timeline id="race" aria-label="The race before and after the fix">
  <lf-run label="Before the fix">
    <lf-lane label="Job A">
      <lf-event id="before-a-work" at="0" end="4200" label="Adds 50"></lf-event>
      <lf-event id="before-a-write" at="4200" label="Writes 150"></lf-event>
    </lf-lane>
    <lf-lane label="Job B">
      <lf-event id="before-b-write" at="5200" label="Writes 70"></lf-event>
    </lf-lane>
  </lf-run>
  <lf-run label="After the fix">
    <lf-lane label="Job A">
      <lf-event id="after-a-work" at="0" end="4200" label="Adds 50"></lf-event>
      <lf-event id="after-a-write" at="4200" label="Writes 150, unlocks"></lf-event>
    </lf-lane>
    <lf-lane label="Job B">
      <lf-event id="after-b-write" at="8500" label="Writes 120, unlocks"></lf-event>
    </lf-lane>
  </lf-run>
</lf-timeline>"""


def test_a_tall_timeline_s_gridlines_reach_its_last_lane(browser, serve):
    """Each major time's line runs from the ruler's foot to the chart's, however many
    lanes the chart holds, as its playhead does."""
    lanes = "".join(
        f'<lf-lane label="Worker {n}"><lf-event id="w{n}" at="{n * 100}" '
        f'end="{n * 100 + 2000}" label="Job {n}"></lf-event></lf-lane>'
        for n in range(60)
    )
    source = leaf_page(
        "Tall",
        f'<h1>Tall</h1><lf-timeline id="tall" aria-label="Workers">{lanes}</lf-timeline>',
    )
    page = open_page(browser, serve(source, packages=("timeline",)))
    reading = page.evaluate(
        """() => {
          const tall = document.querySelector('#tall');
          const box = (node) => node.getBoundingClientRect();
          return {
            chart: box(tall.querySelector('.lf-timeline-chart')),
            ruler: box(tall.querySelector('.lf-timeline-ruler')),
            playhead: box(tall.querySelector('.lf-timeline-playhead-line')),
            lines: [...tall.querySelectorAll('.lf-axis-gridline')].map(box),
          };
        }"""
    )
    assert reading["chart"]["height"] > 2000, reading["chart"]
    assert reading["lines"], reading
    for line in reading["lines"]:
        assert abs(line["top"] - reading["ruler"]["bottom"]) < 0.5, (line, reading)
        assert abs(line["bottom"] - reading["chart"]["bottom"]) < 0.5, (line, reading)
    assert abs(reading["playhead"]["bottom"] - reading["chart"]["bottom"]) < 0.5


def test_compared_runs_line_up_on_one_axis_under_one_playhead(browser, serve):
    page = open_page(browser, serve(leaf_page("Race", RUNS), packages=("timeline",)))
    reading = page.evaluate(
        """() => {
          const race = document.querySelector('#race');
          const box = (selector) => race.querySelector(selector).getBoundingClientRect();
          const mark = (id) => box(`[data-lf-event="${id}"] .lf-timeline-mark`);
          const lanes = [...race.querySelectorAll('.lf-timeline-lane')].map((lane) =>
            lane.getBoundingClientRect());
          const runs = [...race.querySelectorAll('.lf-timeline-run')].map((run) =>
            run.getBoundingClientRect());
          return {
            before: mark('before-a-write'), after: mark('after-a-write'),
            beforeEnd: mark('before-b-write'), afterEnd: mark('after-b-write'),
            playhead: box('.lf-timeline-playhead-line'), lanes, runs,
          };
        }"""
    )
    # The same moment stands at the same x in every run, and the longer run reaches
    # further along the one axis.
    assert abs(reading["before"]["x"] - reading["after"]["x"]) < 0.5, reading
    assert reading["afterEnd"]["x"] > reading["beforeEnd"]["x"] + 50, reading
    # One playhead crosses every run's lanes.
    lanes = reading["lanes"]
    assert reading["playhead"]["top"] <= lanes[0]["top"], reading
    assert reading["playhead"]["bottom"] >= lanes[-1]["bottom"] - 0.5, reading
    # Each run's name stands between the run before it and its own lanes.
    before_run, after_run = reading["runs"]
    assert before_run["bottom"] <= lanes[0]["top"] + 0.5, reading
    assert lanes[1]["bottom"] <= after_run["top"] + 0.5, reading
    assert after_run["bottom"] <= lanes[2]["top"] + 0.5, reading
    assert_labels_clear(page)

    page.locator("#race").get_by_role("button", name="Next").click()
    page.keyboard.press("ArrowRight")
    expect(page.locator(".lf-live")).to_have_text(
        "Step 3 of 4. Before the fix · Job B: Writes 70"
    )


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
    expect(
        page.locator('#race [data-lf-event="a-work"] .lf-timeline-label')
    ).to_have_text("Adds 75")
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
    expect(race.locator('[data-lf-event="a-work"] .lf-timeline-label')).to_have_text(
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
    """Next at the last step is unavailable, and its arrow stays the timeline's: a
    command around it, on the same key, does not run."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Command around a timeline",
                """<h1>Command around a timeline</h1>
<div id="around">
  <button id="beside" type="button">Beside</button>
  <lf-timeline id="tl" aria-label="Two steps">
    <lf-lane label="Build">
      <lf-event id="e1" at="0" label="Compile"></lf-event>
      <lf-event id="e2" at="1000" label="Ship"></lf-event>
    </lf-lane>
  </lf-timeline>
</div>""",
            ),
            packages=("timeline",),
        ),
    )
    page.evaluate("""async () => {
      const {commandsChanged} = await window.__lfWidgetApi();
      const around = document.getElementById('around');
      window.aroundRan = 0;
      around.lfCommands = {title: 'Around the timeline', rows: [{
        id: 'around.next', title: 'Next card', keys: ['ArrowRight'],
        run: () => { window.aroundRan++; },
      }]};
      commandsChanged(around);
    }""")
    # Control: the command does run from the page around the timeline.
    page.locator("#beside").focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_function("window.aroundRan === 1")
    rows = page.locator("#tl .lf-timeline-step")
    rows.last.click()
    expect(rows.last).to_have_attribute("aria-current", "step")
    expect(page.locator("#tl .lf-timeline-next")).to_have_attribute(
        "aria-disabled", "true"
    )
    page.keyboard.press("ArrowRight")
    expect(rows.last).to_be_focused()
    page.evaluate(NEXT_FRAME)
    assert page.evaluate("window.aroundRan") == 1
