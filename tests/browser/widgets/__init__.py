"""Browser tests of the widgets a page declares, one module per widget family or shared
widget mechanism, and the page sources and helpers more than one module uses."""

import re

from playwright.sync_api import expect
from render_cases_widgets import LONG_LINE_DIFF_PAGE, MULTI_HUNK_PATCH
from render_harness import PANEL, leaf_page, open_page, panel_field, panel_menu

from leaf import data as data_model


def expect_walk_says(page, words):
    """Wait for a walk's position, such as "Hunk 2 of 3", to be said where the panel
    says what passes: in its empty field's place (floating-panel.js), as a notice is."""
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile(re.escape(words))
    )


def expect_accept_all(page, count):
    """Read the leaf's menu offering Accept all for `count` pending suggestions, enabled,
    then put the menu away; `count` 0 reads no such row at all."""
    menu = panel_menu(page)
    row = menu.locator('.lf-fp-item[data-row="blanket:accept"]')
    if count:
        expect(row).to_be_enabled()
        expect(row).to_contain_text(f"Accept all ({count})")
    else:
        expect(row).to_have_count(0)
    put_menu_away(page)


def put_menu_away(page):
    """Close the leaf's menu by its leaf, which keeps the focus the press gave it."""
    page.locator(".lf-fp-leaf").click()
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")


def observe_live_region(page):
    """Record announcements without disturbing the renderer-owned live region."""
    page.evaluate(
        """() => {
          const live = document.querySelector('.lf-live');
          const changes = [];
          window.__lfLiveRegionChanges = changes;
          new MutationObserver(() => changes.push(live.textContent))
            .observe(live, {childList: true, characterData: true, subtree: true});
        }"""
    )


PLAYGROUND_PAGE = leaf_page(
    "card playground",
    """
<h1>Card playground</h1>
<style>
  #playground-card {
    --lf-block-frame: 1;
    border: 2px solid var(--playground-accent);
    border-radius: var(--playground-radius);
    padding: 24px;
  }
  #playground-card::before { content: var(--playground-title); }
  #card-playground[data-playground-compact="true"] #playground-card { padding: 8px; }
  #card-playground[data-playground-tone="bold"] #playground-card { font-weight: 700; }
</style>
<lf-ask id="card-playground-ask">
  <h2>How should the card look?</h2>
  <lf-playground id="card-playground">
    <lf-playground-control name="radius" label="Corner radius" kind="range"
      value="12" min="0" max="28" step="1" unit="px"></lf-playground-control>
    <lf-playground-control name="compact" label="Compact spacing" kind="toggle"
      value="false"></lf-playground-control>
    <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
      <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
      <lf-playground-choice value="bold" label="Bold"></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-control name="accent" label="Accent" kind="color"
      value="#4f766f"></lf-playground-control>
    <lf-playground-control name="title" label="Title" kind="text"
      value="Field note" placeholder="Card title"></lf-playground-control>
    <lf-playground-preset label="Dense">
      <lf-playground-setting for="radius" value="4"></lf-playground-setting>
      <lf-playground-setting for="compact" value="true"></lf-playground-setting>
      <lf-playground-setting for="tone" value="bold"></lf-playground-setting>
    </lf-playground-preset>
    <lf-playground-preview id="card-preview">
      <article id="playground-card"><strong>Card preview</strong><p>Open until dusk.</p></article>
    </lf-playground-preview>
    <lf-playground-output id="card-instruction">Use a
      <lf-playground-value for="radius"></lf-playground-value> radius,
      compact spacing set to <lf-playground-value for="compact"></lf-playground-value>,
      a <lf-playground-value for="tone"></lf-playground-value> tone,
      <lf-playground-value for="accent"></lf-playground-value> accents, and the title
      <lf-playground-value for="title"></lf-playground-value>.
    </lf-playground-output>
  </lf-playground>
</lf-ask>
""",
)


def _bound_diff(browser, serve, patch=MULTI_HUNK_PATCH):
    """The review the diff tests below read, with its feed in place before the page loads."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    return page
