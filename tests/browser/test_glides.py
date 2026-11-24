"""Leaf's glides: a landing's glide lands its destination where the page's layout puts
it once the glide ends, however that layout changes during the glide, and a later
landing takes the glide over."""

import pytest
from render_harness import held_frames, leaf_page, open_page, scroll_settled

FILLER = "".join(
    f"<p>Paragraph {i}. " + "Words to read. " * 20 + "</p>" for i in range(30)
)

PAGE = leaf_page(
    "Glides",
    f"""
<h1 id="top">Glides</h1>
<p><button id="press" type="button" style="position: fixed; bottom: 1rem; right: 1rem">
  Land</button></p>
<div id="above" style="height: 40px"></div>
<h2 id="up">Up</h2>
{FILLER}
<div id="between" style="height: 40px"></div>
{FILLER}
<p id="start">The press starts here.</p>
{FILLER}
<div id="below" style="height: 40px"></div>
<h2 id="down">Down</h2>
{FILLER}
<div id="end"><div id="taller"></div><p>End</p></div>
{FILLER}
""",
)

# The press lands a destination smoothly, as a widget brings what it shows into view,
# and changes boxes' heights in the same task, as a list the press redraws changes.
PRESS = """async ([to, block, changes]) => {
  const { scrollIntoView } = await window.__lfWidgetApi();
  document.getElementById('press').addEventListener('click', () => {
    scrollIntoView(document.getElementById(to), { block, behavior: 'smooth' });
    for (const [id, height] of changes)
      document.getElementById(id).style.height = `${height}px`;
  });
}"""


@pytest.mark.parametrize(
    ("to", "block", "changes"),
    [
        # Above the window and below the destination: scroll anchoring would move the
        # page and leave the destination.
        ("top", "start", [("between", 62)]),
        # Above the destination and the window.
        ("up", "start", [("above", 62)]),
        # Below the window and above the destination.
        ("down", "start", [("below", 62)]),
        # Above the window and below it, by as much: anchoring would move the page by
        # what the page's height doesn't change by.
        ("top", "start", [("between", 62), ("below", 18)]),
        # In the destination, above the end a landing at its end aligns.
        ("end", "end", [("taller", 80)]),
    ],
    ids=["below-destination", "above-destination", "below-window", "cancelling", "end"],
)
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_landing_s_glide_lands_its_destination_where_layout_moves_it(
    request, serve, engine, to, block, changes
):
    """A press that lands a destination smoothly, and changes the heights of boxes as it
    does, glides to where an instant landing then would leave the destination, though
    the change moves the destination under the glide or would have scroll anchoring
    move the page."""
    page = open_page(request.getfixturevalue(engine), serve(PAGE))
    page.set_viewport_size({"width": 1000, "height": 700})
    page.evaluate(PRESS, [to, block, changes])
    page.locator("#start").scroll_into_view_if_needed()
    scroll_settled(page)
    with held_frames(page) as step:
        page.locator("#press").click()
        step(12)
    scroll_settled(page)
    landed = page.evaluate(
        """async ([to, block]) => {
          const { scrollIntoView } = await window.__lfWidgetApi();
          const at = scrollY;
          scrollIntoView(document.getElementById(to), { block, behavior: 'instant' });
          return { at, still: scrollY };
        }""",
        [to, block],
    )
    assert landed["still"] == landed["at"], landed


# Two columns, with a heading in each, and a box above each heading.
SECOND = leaf_page(
    "Second landing",
    """
<h1>Second landing</h1>
<p><button id="press" type="button" style="position: fixed; bottom: 1rem; right: 1rem">
  Land</button></p>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem">
  <div>
    <div style="height: 2000px"></div>
    <div id="above" style="height: 10px"></div>
    <div style="height: 1000px"></div>
    <h2 id="first">First</h2>
    <div style="height: 3000px"></div>
  </div>
  <div>
    <div style="height: 3100px"></div>
    <div id="over-second" style="height: 10px"></div>
    <h2 id="second">Second</h2>
    <div style="height: 3000px"></div>
  </div>
</div>
""",
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_second_landing_takes_the_glide_the_first_set_off(request, serve, engine):
    """A landing on a heading the window shows, and will show where a glide under way
    lands, moves nothing at once, and takes that glide from the landing that set it off.
    Content that then grows above both headings, more above the first, leaves the page
    where it shows the second, rather than where the first's heading went, or where the
    first landing aimed, or where the glide stood."""
    page = open_page(request.getfixturevalue(engine), serve(SECOND))
    page.set_viewport_size({"width": 1000, "height": 700})
    page.evaluate(
        """async () => {
          const { scrollIntoView } = await window.__lfWidgetApi();
          const first = document.getElementById('first');
          scrollTo(0, first.getBoundingClientRect().top + scrollY - 300);
          document.getElementById('press').addEventListener('click', () => {
            scrollIntoView(first, { block: 'start', behavior: 'smooth' });
            scrollIntoView(document.getElementById('second'),
              { block: 'nearest', behavior: 'smooth' });
            document.getElementById('above').style.height = '1210px';
            document.getElementById('over-second').style.height = '810px';
          });
        }"""
    )
    scroll_settled(page)
    with held_frames(page) as step:
        page.locator("#press").click()
        step(12)
    scroll_settled(page)
    landed = page.evaluate(
        """async () => {
          const { scrollIntoView } = await window.__lfWidgetApi();
          const at = scrollY;
          scrollIntoView(document.getElementById('second'),
            { block: 'nearest', behavior: 'instant' });
          return { at, still: scrollY };
        }"""
    )
    assert landed["still"] == landed["at"], landed


@pytest.mark.parametrize(
    ("grown", "style"),
    [
        ("below", "height: 190px"),
        ("down", "padding-bottom: 80px"),
        # Undrawn for the glide's first frames, as content grows above it.
        ("down", "display: none"),
    ],
    ids=["above-subject", "subject", "hidden"],
)
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_card_s_room_made_past_a_landing_holds_as_layout_moves_its_subject(
    request, serve, engine, grown, style
):
    """A press that lands a heading at the window's centre and opens a card 420px tall
    under it glides to where the card fits under the heading, though content above the
    heading, or the heading itself, then grows as the page glides (comment-placement.js,
    `makeRoom`), or the heading is briefly not drawn."""
    page = open_page(request.getfixturevalue(engine), serve(PAGE))
    page.set_viewport_size({"width": 1000, "height": 700})
    page.evaluate(
        """async ([grown, style]) => {
          const { scrollIntoView } = await window.__lfWidgetApi();
          const { makeRoom, subjectGap } = await window.__lfOverlayApi();
          const subject = document.getElementById('down');
          const room = { left: 8, top: 8, right: 8, bottom: 8 };
          window.boundary = () => ({ top: 0, bottom: innerHeight, height: innerHeight });
          window.left = () => {
            const { bottom } = subject.getBoundingClientRect();
            return boundary().bottom - bottom - subjectGap(room, 'bottom') - 420;
          };
          document.getElementById('press').addEventListener('click', () => {
            scrollIntoView(subject, { block: 'center', behavior: 'smooth' });
            const read = () => {
              const clear = subject.getBoundingClientRect();
              return subject.checkVisibility()
                ? { clear, extent: clear, room, element: subject }
                : null;
            };
            makeRoom('bottom', read, 420, boundary(), document.scrollingElement);
            document.getElementById(grown).style.cssText += style;
            if (style === 'display: none')
              document.getElementById('below').style.height = '190px';
          });
        }""",
        [grown, style],
    )
    page.locator("#start").scroll_into_view_if_needed()
    scroll_settled(page)
    with held_frames(page) as step:
        page.locator("#press").click()
        step(3)
        page.evaluate("document.getElementById('down').style.display = ''")
        step(9)
    scroll_settled(page)
    assert page.evaluate("left()") == pytest.approx(0, abs=1)
