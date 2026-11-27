"""An age an author writes (`lf-age`) is drawn over the time they wrote, which stays
the page's words."""

import pytest
from model_folds import leaf_page
from render_harness import open_page

AGES = leaf_page(
    "Ages",
    '<h1>Runs</h1><p id="ran">The import last ran <lf-age datetime="2026-11-20T02:10:00Z"'
    ">20 Nov, 02:10 UTC</lf-age>, and nothing has failed since.</p>",
)

# What the page's comment capture reads of the selection (dom/native-selection.js,
# `pageRange`): the anchor it would quote, or null where the selection is a caret.
SELECTED = """async () => {
  const { anchorForRange, pageRange } = await window.__lfCheckApi();
  const range = pageRange(getSelection());
  return range.collapsed ? null : anchorForRange(range);
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_an_age_is_quoted_by_the_time_its_author_wrote(engine, request, serve):
    """The reader sees how long ago, and the page's reading keeps the time the file
    holds: a double-click on the age's figure quotes that time, so a comment on an age
    keeps its passage when the age ticks. Firefox selects the figure because a
    zero-width no-break space leads the drawn words (age.js): with them flush against
    their host's start it selects nothing there."""
    page = open_page(request.getfixturevalue(engine), serve(AGES))
    age = page.locator("#ran lf-age")
    drawn = age.evaluate("age => age.shadowRoot.textContent.trim()")
    assert drawn.endswith("d ago"), drawn
    box = age.bounding_box()
    # Its first word, the figure.
    page.mouse.dblclick(box["x"] + 6, box["y"] + box["height"] / 2)
    anchor = page.evaluate(SELECTED)
    assert anchor and anchor["quote"] == "20 Nov, 02:10 UTC", anchor
