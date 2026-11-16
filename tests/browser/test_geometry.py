"""Visible geometry keeps the platform's hidden and boxless states distinct."""

from playwright.sync_api import expect
from render_harness import leaf_page, open_page


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
