"""Browser tests of comment marks, Go-to addresses and keyboard navigation, with the
page constants and helpers their modules share."""

from render_harness import leaf_page, regions_side_by_side

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


# Where the user is standing, in the terms the next Tab is decided by: the document
# position of the focused element, and whether it is the first stop in the document.
STANDING = """() => {
  const at = document.activeElement;
  const first = document.querySelector('.lf-skip');
  return {
    name: at?.className || at?.tagName || 'nothing',
    isFirstStop: at === first,
    top: at ? at.getBoundingClientRect().top : null,
    inChrome: Boolean(at?.closest?.('.lf-chrome')),
  };
}"""
