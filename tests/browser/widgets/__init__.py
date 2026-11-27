"""Browser tests of the widgets a page declares, one module per widget family or shared
widget mechanism, and the page sources and helpers more than one module uses."""

from playwright.sync_api import expect
from render_cases_widgets import LONG_LINE_DIFF_PAGE, MULTI_HUNK_PATCH
from render_harness import (
    close_panel_menu,
    leaf_page,
    open_page,
    panel_menu,
)

from leaf.records import page_data as page_data_model


def expect_walk_says(page, words):
    """Wait for a walk's position, such as "Hunk 2 of 3", to be heard: a step announces
    it whether or not the panel's field shows it, which it does only while the list
    runs past the window (records/walk-position.js, `stepTo`)."""
    expect(page.locator(".lf-live")).to_contain_text(words)


def hear_walks(page):
    """Start recording the places a widget's steps say to the page (`lf-walk`,
    module-input.md, "Walks"), as the window hears them, for `walks_said`. An `lf-walk`
    saying the user has left a stop carries no place, and is not recorded."""
    page.evaluate(
        """() => {
          window.__lfWalksSaid = [];
          addEventListener('lf-walk', ({detail}) => detail && window.__lfWalksSaid.push(
            `${detail.noun} ${detail.position} of ${detail.total}`));
        }"""
    )


def walks_said(page):
    """Each place said since `hear_walks`, in order, as "Hunk 2 of 3"."""
    return page.evaluate("() => window.__lfWalksSaid")


def expect_accept_all(page, count):
    """Read the leaf's menu offering Accept all for `count` pending suggestions, enabled,
    then put the menu away; `count` 0 reads no such row at all."""
    menu = panel_menu(page)
    row = menu.locator('.lf-fp-item[data-lf-row="blanket:accept"]')
    if count:
        expect(row).to_be_enabled()
        expect(row).to_contain_text(f"Accept all ({count})")
    else:
        expect(row).to_have_count(0)
    close_panel_menu(page)


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
    border-radius: calc(var(--playground-radius) * 1px);
    padding: 24px;
  }
  #playground-card::before { content: var(--playground-title); }
  #card-playground[data-playground-compact="true"] #playground-card { padding: 8px; }
  #card-playground[data-playground-tone="bold"] #playground-card { font-weight: 700; }
</style>
<lf-group id="card-playground-ask" label="How should the card look?">
  <h2 id="card-playground-ask-h">How should the card look?</h2>
  <lf-playground id="card-playground">
    <aside>
      <label id="radius">Corner radius <input type="range" name="radius"
        min="0" max="28" value="12"></label>
      <label id="compact"><input type="checkbox" name="compact"
        role="switch"> Compact spacing</label>
      <fieldset id="tone"><legend>Tone</legend>
        <label id="tone-quiet"><input type="radio" name="tone"
          value="quiet" checked> Quiet</label>
        <label id="tone-bold"><input type="radio" name="tone"
          value="bold"> Bold</label>
      </fieldset>
      <label id="accent">Accent <input type="color" name="accent" value="#4f766f"></label>
      <label id="title">Title <input name="title" value="Field note"
        placeholder="Card title"></label>
    </aside>
    <lf-playground-preset id="preset-dense" label="Dense">
      <lf-playground-setting for="radius" value="4"></lf-playground-setting>
      <lf-playground-setting for="compact" value="true"></lf-playground-setting>
      <lf-playground-setting for="tone" value="bold"></lf-playground-setting>
    </lf-playground-preset>
    <article id="playground-card"><strong>Card preview</strong><p>Open until dusk.</p></article>
    <lf-playground-output id="card-instruction">Use a
      <output for="radius"></output>px radius,
      compact spacing set to <output for="compact"></output>,
      a <output for="tone"></output> tone,
      <output for="accent"></output> accents, and the title
      <output for="title"></output>.
    </lf-playground-output>
  </lf-playground>
</lf-group>
""",
)


def _bound_diff(browser, serve, patch=MULTI_HUNK_PATCH):
    """The review the diff tests below read, with its feed in place before the page loads."""
    url = serve(LONG_LINE_DIFF_PAGE)
    page_data_model.cmd_data_set(serve.page_dir, "review-patch", patch)
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    return page
