"""Leaf's glides: a landing's glide goes on through the moves layout makes under it."""

import pytest
from render_harness import held_frames, leaf_page, open_page, scroll_settled

FILLER = "".join(
    f"<p>Paragraph {i}. " + "Words to read. " * 20 + "</p>" for i in range(30)
)

PAGE = leaf_page(
    "Glides",
    f"""
<h1 id="top">Glides</h1>
{FILLER}
<div id="list" style="height: 10px"></div>
{FILLER}
<p><button id="press" type="button">Top</button></p>
""",
)

# The press lands the heading smoothly, as a widget brings what it shows into view, and
# grows a list above the window as it does, as a list the press redraws grows.
PRESS = """() => document.getElementById('press').addEventListener('click', async () => {
  const { scrollIntoView } = await window.__lfWidgetApi();
  scrollIntoView(document.getElementById('top'), { block: 'start', behavior: 'smooth' });
  document.getElementById('list').style.height = '32px';
})"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_landing_s_glide_goes_on_as_scroll_anchoring_moves_the_page(
    request, serve, engine
):
    """A press that lands a heading smoothly, and grows content between the heading and
    the window as it does, glides to the heading where an instant landing would leave
    it, though scroll anchoring moves the page under the glide as the content grows."""
    page = open_page(request.getfixturevalue(engine), serve(PAGE))
    page.set_viewport_size({"width": 1000, "height": 700})
    page.evaluate(PRESS)
    press = page.locator("#press")
    press.scroll_into_view_if_needed()
    scroll_settled(page)
    with held_frames(page) as step:
        press.click()
        step(12)
    scroll_settled(page)
    landed = page.evaluate(
        """async () => {
          const { scrollIntoView } = await window.__lfWidgetApi();
          const at = scrollY;
          scrollIntoView(document.getElementById('top'),
            { block: 'start', behavior: 'instant' });
          return { at, still: scrollY };
        }"""
    )
    assert landed["still"] == landed["at"], landed
