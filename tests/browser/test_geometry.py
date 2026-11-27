"""Visible geometry keeps the platform's hidden and boxless states distinct."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, scroll_settled


def test_hidden_boxes_keep_native_bounds_until_tabs_reveal(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Hidden and boxless bounds",
                """
<h1>Evidence</h1>
<lf-tabs id="evidence-views">
  <lf-tab id="summary" label="Summary"><p>The current summary.</p></lf-tab>
  <lf-tab id="outer" label="Evidence">
    <lf-tabs id="saved-views">
      <lf-tab id="overview" label="Overview"><p>Evidence overview.</p></lf-tab>
      <lf-tab id="inner" label="Saved">
        <p id="destination">Saved evidence becomes readable here.</p>
      </lf-tab>
    </lf-tabs>
  </lf-tab>
</lf-tabs>
<div id="contents" style="display: contents"><p>Visible boxless evidence.</p></div>
<div id="zero" style="width: 0; height: 0; white-space: nowrap">Overflowing words.</div>
""",
            )
        ),
    )
    boxes = """async () => {
      const {shownBox} = await window.__lfCheckApi();
      return Object.fromEntries(['outer', 'inner', 'destination', 'contents', 'zero'].map(id => {
        const el = document.getElementById(id);
        const box = shownBox(el);
        const native = el.getBoundingClientRect();
        return [id, {width: box.width, height: box.height, visible: el.checkVisibility(),
                     nativeWidth: native.width, nativeHeight: native.height}];
      }));
    }"""
    before = page.evaluate(boxes)
    for key in ("outer", "inner", "destination"):
        box = before[key]
        assert box["width"] == box["nativeWidth"], before
        assert box["height"] == box["nativeHeight"], before
    expect(page.locator("#outer")).to_have_attribute("hidden", "until-found")
    expect(page.locator("#inner")).to_have_attribute("hidden", "until-found")
    assert not before["destination"]["visible"]
    assert before["contents"]["nativeWidth"] == before["contents"]["nativeHeight"] == 0
    assert before["contents"]["width"] > 0 and before["contents"]["height"] > 0
    assert before["zero"]["width"] == before["zero"]["nativeWidth"] == 0
    assert before["zero"]["height"] == before["zero"]["nativeHeight"] == 0

    page.get_by_role("tab", name="Evidence", exact=True).click()
    page.get_by_role("tab", name="Saved", exact=True).click()
    expect(page.locator("#destination")).to_be_visible()
    after = page.evaluate(boxes)
    for key in ("outer", "inner", "destination", "contents"):
        box = after[key]
        assert box["width"] > 0 and box["height"] > 0


# The runtime's scroll readings and glides, imported into the page as `S` and `G`.
IMPORTS = """
  const entry = new URL(
    document.querySelector('script[data-lf-entry]').dataset.lfEntry, location.href);
  const S = await import(new URL('runtime/readings/scroll-containers.js', entry).href);
  const G = await import(new URL('runtime/dom/scrolling.js', entry).href);
"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize(
    ("above", "into", "start", "region", "root"),
    [(600, 500, 0, 450, 300), (400, 400, 300, 300, 0)],
    ids=["carried-in", "carried-nowhere"],
)
def test_a_node_two_glides_bring_into_view_is_seen_where_they_land(
    request, serve, engine, above, into, start, region, root
):
    """A glide of an inner region that brings a node into the region's view, while a
    glide of the page brings the region into the window, leaves the node seen: it is
    read where both glides land, its region's clip included, rather than cut by that
    clip as it stands and then carried. So is one the two glides carry nowhere, the
    region's glide down taking back the page's glide up, while they bring the region's
    view over it."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Two glides",
                f'<h1>Two glides</h1><div style="height: {above}px"></div>'
                '<div id="inner" style="height: 300px; overflow-y: auto;'
                f' --lf-reading-region: layout"><div style="height: {into}px"></div>'
                '<button id="target">Target</button><div style="height: 1000px"></div>'
                '</div><div style="height: 2000px"></div>',
            )
        ),
    )
    page.set_viewport_size({"width": 1200, "height": 800})
    page.evaluate(f"scrollTo({{top: {start}, behavior: 'instant'}})")
    scroll_settled(page)
    seen = page.evaluate(
        "async ([region, root]) => {"
        + IMPORTS
        + """
          const target = document.getElementById('target');
          const atRest = S.seenLanded(target);
          G.glideTo(document.getElementById('inner'), region);
          G.glideTo(document.documentElement, root);
          return {atRest, ahead: S.seenLanded(target)};
        }""",
        [region, root],
    )
    assert seen == {"atRest": False, "ahead": True}
    expect(page.locator("#target")).to_be_in_viewport()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_card_anchored_to_the_page_rides_its_glide_with_the_clip_it_holds(
    request, serve, engine
):
    """A box fixed over the page and anchored to a node in it, as a thread card is,
    rides the page's glide whole, though it takes the scroll only at the next frame. So
    where the glide leaves it, its own clip still hides what it held out of view, while
    the card itself is seen."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Anchored card",
                '<h1>Anchored card</h1><div style="height: 500px"></div>'
                '<p id="anchor">Anchor</p>'
                '<div style="height: 3000px"></div>',
            )
        ),
    )
    page.set_viewport_size({"width": 1200, "height": 800})
    seen = page.evaluate(
        "async () => {"
        + IMPORTS
        + """
          const C = await import(new URL('runtime/dom/css-anchors.js', entry).href);
          // Beside the body, as the chrome stands, so the window holds it.
          const card = document.createElement('div');
          card.style.cssText = 'position: fixed; top: anchor(top); left: 400px;'
            + ' width: 200px; height: 100px; overflow-y: auto';
          card.style.positionAnchor = C.anchorName(document.getElementById('anchor'));
          card.innerHTML = '<div style="height: 200px"></div>'
            + '<button id="held">Held</button><div style="height: 300px"></div>';
          document.documentElement.append(card);
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          G.glideTo(document.documentElement, 100);
          const held = document.getElementById('held');
          return {
            card: S.seenLanded(card),
            held: S.seenLanded(held),
            anchored: S.glideTravel(held)?.held?.fixed === card,
          };
        }"""
    )
    assert seen == {"card": True, "held": False, "anchored": True}
