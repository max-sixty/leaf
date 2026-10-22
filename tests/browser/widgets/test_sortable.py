"""Public Sortable plugins preserve every card when a pointer gesture is cancelled."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("plugin", ["Swap", "MultiDrag"])
def test_plugin_cancellation_restores_all_cards_and_allows_the_next_drag(
    browser, serve, plugin
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Sortable plugins",
                """
<h1 id="title">Cards</h1>
<div id="lists">
  <ul id="source"><li id="a">A</li><li class="stationary" id="stay">Stationary</li><li id="b">B</li><li id="c">C</li></ul>
  <ul id="target"><li id="d">D</li><li id="e">E</li></ul>
</div>
""",
                head="""<style>
#lists { display: flex; gap: 40px; }
#lists ul { width: 240px; min-height: 240px; padding: 0; list-style: none; }
#lists li { height: 60px; border: 1px solid; box-sizing: border-box; }
</style>""",
            )
        ),
    )
    page.evaluate(
        """async plugin => {
          const vendor = await import('/vendor/sortable.esm.js');
          const Sortable = vendor.default;
          Sortable.mount(new vendor[plugin]());
          window.sortableReview = {
            Sortable,
            cards: [...document.querySelectorAll('#lists li')],
            ends: [], sorts: 0, saves: 0,
          };
          for (const list of document.querySelectorAll('#lists ul')) {
            new Sortable(list, {
              group: 'cards', draggable: 'li:not(.stationary)', forceFallback: true,
              animation: 150, removeCloneOnHide: false,
              [plugin === 'Swap' ? 'swap' : 'multiDrag']: true,
              onEnd: evt => sortableReview.ends.push(evt.cancelled),
              onSort: () => sortableReview.sorts++,
              store: {set: () => sortableReview.saves++},
            });
          }
        }""",
        plugin,
    )

    if plugin == "MultiDrag":
        page.locator("#a").click()
        page.locator("#b").click()
        source = page.locator("#a").bounding_box()
        page.mouse.move(source["x"] + 100, source["y"] + 30)
        page.mouse.down()
        page.evaluate("""() => document.dispatchEvent(new PointerEvent('pointercancel', {
          bubbles: true, pointerId: 1, pointerType: 'mouse',
        }))""")
        page.mouse.up()
        expect(page.locator("#source > .sortable-selected")).to_have_text(["A", "B"])
        assert page.evaluate("sortableReview.ends") == []

    def drag_to_target():
        if plugin == "MultiDrag":
            for card in ("#a", "#b"):
                if "sortable-selected" not in (
                    page.locator(card).get_attribute("class") or ""
                ):
                    page.locator(card).click()
        source = page.locator("#a").bounding_box()
        target = page.locator("#e").bounding_box()
        page.mouse.move(source["x"] + 100, source["y"] + 30)
        page.mouse.down()
        page.mouse.move(target["x"] + 100, target["y"] + target["height"] - 5, steps=16)
        expect(page.locator(".sortable-fallback")).to_have_count(1)
        if plugin == "Swap":
            expect(page.locator("#e")).to_have_class("sortable-swap-highlight")
        else:
            page.wait_for_function("sortableReview.cards[0].parentNode.id === 'target'")

    drag_to_target()
    page.evaluate("""() => sortableReview.Sortable.get(
      document.querySelector('#source')
    ).cancel()""")
    page.mouse.up()
    page.wait_for_function(
        "sortableReview.cards.every(card => !card.animated && !card.thisAnimationDuration)"
    )
    expect(page.locator("#source > li")).to_have_text(["A", "Stationary", "B", "C"])
    expect(page.locator("#target > li")).to_have_text(["D", "E"])
    expect(page.locator(".sortable-fallback, .sortable-swap-highlight")).to_have_count(
        0
    )
    assert page.evaluate("""() => {
      const {cards, Sortable, ends, sorts, saves} = sortableReview;
      return {
        originalNodes: cards.every(card => document.getElementById(card.id) === card),
        active: Boolean(Sortable.active), ends, sorts, saves,
      };
    }""") == {
        "originalNodes": True,
        "active": False,
        "ends": [True],
        "sorts": 0,
        "saves": 0,
    }

    drag_to_target()
    page.mouse.up()
    if plugin == "Swap":
        expect(page.locator("#source > li")).to_have_text(["E", "Stationary", "B", "C"])
        expect(page.locator("#target > li")).to_have_text(["D", "A"])
    else:
        expect(page.locator("#source > li")).to_have_text(["Stationary", "C"])
        expect(page.locator("#target > li")).to_have_text(["D", "E", "A", "B"])
    expect(page.locator(".sortable-fallback, .sortable-swap-highlight")).to_have_count(
        0
    )
    assert page.evaluate("sortableReview.ends") == [True, False]
