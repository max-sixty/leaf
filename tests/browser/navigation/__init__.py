"""Browser tests of comment marks, Go-to addresses and keyboard navigation, with the
page constants and helpers their modules share."""

from render_harness import leaf_page, regions_side_by_side

from leaf.render_checks import rendered

READING_REGIONS_PAGE = leaf_page(
    "reading region navigation",
    """
  <header><h1>Reading workspace</h1></header>
  <div id="reading-split">
    <lf-pane id="left-reading" label="Left reading">
      <header><button id="left-head">Left header</button></header>
      <div>
        <p id="left-start">Left start with enough words to preserve this landmark.</p>
        <div style="height: 260px"></div>
        <p id="left-landmark">The current left reading has a stable semantic landmark.</p>
        <div style="height: 800px"></div>
        <p id="left-end">Left end</p>
      </div>
      <footer><button id="left-foot">Left footer</button></footer>
    </lf-pane>
    <lf-pane id="right-reading" label="Right reading">
      <header><button id="right-head">Right header</button></header>
      <div>
        <p id="right-start">Right start with enough words to preserve this landmark.</p>
        <div style="height: 320px"></div>
        <p id="right-landmark">The current right reading has a stable semantic landmark.</p>
        <div style="height: 740px"></div>
        <p id="right-end"><button id="right-subject">Right subject</button></p>
      </div>
    </lf-pane>
  </div>
""",
    head=regions_side_by_side("reading-split"),
    layout="workspace",
)


def color_cue_markup():
    return leaf_page(
        "Color cue surfaces",
        '<h1>Review</h1><section id="review"><lf-tabs id="views">'
        + "".join(
            f'<lf-tab id="{name}" label="{name}">'
            f'<lf-ask id="ask-{name}"><h2>Choose {name}?</h2>'
            f'<lf-options id="choice-{name}" choose>'
            f'<lf-option id="yes-{name}">Yes</lf-option>'
            f'<lf-option id="no-{name}">No</lf-option></lf-options>'
            "</lf-ask></lf-tab>"
            for name in ("first", "second")
        )
        + "</lf-tabs></section>",
    )


# The keyboard walk's position, the reading the panel says in its field's place
# (walk-position.js, `walkPosition`): `{text, kind, target}`, or null with no walk
# under way. Evaluating it leaves a synchronous reader for `wait_for_function`.
WALK_POSITION = """async () => {
  const {walkPosition} = await window.__lfCheckApi();
  window.__lfWalkPosition = () => walkPosition();
  return walkPosition();
}"""


def walk_position(page):
    """The walk's current position, or None with no walk."""
    return page.evaluate(WALK_POSITION)


def expect_walk_position(page, text):
    """Wait until the walk says `text` ("1 of 4 waiting on me · Options"), or, with None,
    until no walk is under way."""
    page.evaluate(WALK_POSITION)
    page.wait_for_function(
        "text => (window.__lfWalkPosition()?.text ?? null) === text", arg=text
    )


# Each route the dispatcher would run from the current location, by the route's own id
# (a parameterized command's route rather than its row, `page.down` rather than
# `page.move`), with the keys that reach it: the reading the bottom key line painted.
OFFERED_ROUTES = """async () => {
  const {availableCommandRoutes, commandEntries} = await window.__lfCheckApi();
  const offered = {};
  for (const [row, bindings] of availableCommandRoutes())
    for (const entry of commandEntries(row, [...bindings]))
      (offered[entry.id] ??= []).push(entry.binding);
  return offered;
}"""


def offered_routes(page):
    """`{route id: [keys]}` the dispatcher would run from the current location now."""
    rendered(page)
    return page.evaluate(OFFERED_ROUTES)
