"""The browser fixture fails what the "Shared containers determine control dimensions" rule
forbids (`swap_watch.js`): a place that changes size as one occupant gives way to
another."""

from urllib.parse import quote

import pytest
from render_harness import consume_browser_errors, judge_watches

from leaf.render_checks import one_frame

# A row seating one occupant at a time. A press on Swap puts the other in its place, the
# way the page's `data-swap` says: by replacing the node, by moving in one that stood on
# the shelf, by hiding one and showing the other, or over two of the page's tasks in one
# frame. `data-tall` makes the second occupant taller than the row's line.
ROW = """<!doctype html><body style="margin:0">
<div id="row" style="display:flex;flex-wrap:wrap;align-items:center;gap:4px;width:300px">
  <button id="first" style="height:24px">First</button>
  <button id="second" style="height:24px" hidden>Second</button>
</div>
<button id="swap">Swap</button>
<div id="shelf"></div>
<script>
  const row = document.getElementById("row");
  const first = document.getElementById("first");
  const second = document.getElementById("second");
  document.getElementById("swap").addEventListener("click", () => {
    const { swap, tall } = document.body.dataset;
    if (tall) second.style.height = "40px";
    if (swap === "replace" || swap === "move") {
      second.hidden = false;
      first.replaceWith(second);
    }
    if (swap === "show") { first.hidden = true; second.hidden = false; }
    if (swap === "frame") {
      first.remove();
      requestAnimationFrame(() => { second.hidden = false; });
    }
  });
</script>"""


def row_page(browser, swap, tall):
    page = browser.new_page()
    page.goto("data:text/html," + quote(ROW))
    page.evaluate(
        "([swap, tall]) => Object.assign(document.body.dataset, tall ? {swap, tall} : {swap})",
        [swap, tall],
    )
    if swap == "move":
        page.evaluate(
            "() => { const second = document.getElementById('second');"
            " second.style.height = '40px'; second.hidden = false;"
            " document.getElementById('shelf').append(second); }"
        )
        one_frame(page)
    return page


@pytest.mark.parametrize("swap", ["replace", "move", "show", "frame"])
def test_an_occupant_that_grows_its_place_fails(browser, swap):
    page = row_page(browser, swap, tall=True)
    page.locator("#swap").click()
    judge_watches()
    consume_browser_errors(
        page,
        {
            "code": "place-resized",
            "place": ["div#row"],
            "left": [["button#first"]],
            "arrived": [["button#second"]],
            "before": {"width": 300, "height": 24},
            "after": {"width": 300, "height": 40},
            "input": "click",
        },
    )


def test_a_row_drawn_in_one_frame_that_its_next_occupant_grows_fails(browser):
    """A row the page draws in an animation frame is watched from that frame, at the
    size it paints there, so an occupant the next frame swaps in that grows it is
    caught. Watched from the frame after instead, the row's first size was the grown
    one."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote('<!doctype html><body style="margin:0"><div id="holder"></div>')
    )
    page.evaluate(
        """() => new Promise((done) => requestAnimationFrame(() => {
          holder.innerHTML = '<div id="row" style="display:flex;width:300px">'
            + '<button id="first" style="height:24px">First</button></div>';
          requestAnimationFrame(() => {
            const second = document.createElement('button');
            Object.assign(second, {id: 'second', textContent: 'Second'});
            second.style.height = '40px';
            first.replaceWith(second);
            requestAnimationFrame(() => requestAnimationFrame(done));
          });
        }))"""
    )
    judge_watches()
    consume_browser_errors(
        page,
        {
            "code": "place-resized",
            "place": ["div#row"],
            "left": [["button#first"]],
            "arrived": [["button#second"]],
        },
    )


# A page with a flex row's holder at its top and a deeply nested box its own
# ResizeObservers watch.
DEEP = (
    '<!doctype html><body style="margin:0"><div id="holder"></div>'
    "<div><div><div><div><div>"
    '<div id="deep" style="width:10px;height:10px"></div>'
    "</div></div></div></div></div>"
)
# Observer A draws the row with a 24px occupant and observer B, delivering after it in
# the same update, makes that occupant 40px, so the frame paints 40px; the next frame
# swaps it for another 40px occupant.
RESIZED_IN_DELIVERY = """() => new Promise((done) => {
  let drawn = false, grown = false;
  new ResizeObserver(() => {
    if (drawn) return;
    drawn = true;
    holder.innerHTML = '<div id="row" style="display:flex;width:300px">'
      + '<button id="first" style="height:24px">First</button></div>';
  }).observe(deep);
  new ResizeObserver(() => {
    if (grown) return;
    grown = true;
    first.style.height = '40px';
    requestAnimationFrame(() => {
      const second = document.createElement('button');
      Object.assign(second, {id: 'second', textContent: 'Second'});
      second.style.height = '40px';
      first.replaceWith(second);
      requestAnimationFrame(() => requestAnimationFrame(done));
    });
  }).observe(deep);
})"""
# A task the page queued in an animation frame that also delivers sizes runs after
# that frame's paint: it draws the row with a 24px occupant, and the next frame swaps
# it for a 40px one before the 24px one is ever painted.
UNPAINTED = """() => new Promise((done) => {
  requestAnimationFrame(() => {
    setTimeout(() => {
      holder.innerHTML = '<div id="row" style="display:flex;width:300px">'
        + '<button id="first" style="height:24px">First</button></div>';
      requestAnimationFrame(() => {
        const second = document.createElement('button');
        Object.assign(second, {id: 'second', textContent: 'Second'});
        second.style.height = '40px';
        first.replaceWith(second);
        requestAnimationFrame(() => requestAnimationFrame(done));
      });
    });
    new ResizeObserver(() => {}).observe(deep);
  });
})"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize(
    "script", [RESIZED_IN_DELIVERY, UNPAINTED], ids=["resized", "unpainted"]
)
def test_a_row_is_judged_by_the_arrangement_it_was_painted_in(engine, request, script):
    """A row's first arrangement is the one a frame painted: one another delivery of
    the same update resized before its paint stands at that size, and one drawn after a
    paint and swapped before the next was never painted, so neither swap grows what
    the user saw."""
    page = request.getfixturevalue(engine).new_page()
    page.goto("data:text/html," + quote(DEEP))
    one_frame(page)
    page.evaluate(script)
    judge_watches()


# A row drawn in a frame inside a holder scaled to 96%, whose 40px occupant the next
# frame swaps for another 40px one: what is displayed stays 38.4px tall.
SCALED = """() => new Promise((done) => {
  holder.style.transform = 'scale(.96)';
  holder.style.transformOrigin = '0 0';
  requestAnimationFrame(() => {
    holder.innerHTML = '<div id="row" style="display:flex;width:300px">'
      + '<button id="first" style="height:40px">First</button></div>';
    requestAnimationFrame(() => {
      const second = document.createElement('button');
      Object.assign(second, {id: 'second', textContent: 'Second'});
      second.style.height = '40px';
      first.replaceWith(second);
      requestAnimationFrame(() => requestAnimationFrame(done));
    });
  });
})"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_scaled_row_whose_occupant_keeps_its_size_passes(engine, request):
    """A row under a transform keeps the size the user sees when an occupant of the
    same size takes its place, measured in one coordinate system throughout."""
    page = request.getfixturevalue(engine).new_page()
    page.goto("data:text/html," + quote(DEEP))
    one_frame(page)
    page.evaluate(SCALED)
    judge_watches()


def test_an_occupant_that_grows_a_declarative_shadow_row_fails(browser):
    """A row the parser builds from a declarative shadow template is watched too."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0">'
            '<div id="row" style="display:flex;width:300px">'
            '<template shadowrootmode="open">'
            '<button id="first" style="height:24px">First</button>'
            '<button id="second" style="height:40px" hidden>Second</button>'
            "</template></div><button id=swap>Swap</button><script>"
            "swap.addEventListener('click', () => {"
            " const seat = id => row.shadowRoot.getElementById(id);"
            " seat('first').hidden = true; seat('second').hidden = false; });"
            "</script>"
        )
    )
    page.locator("#swap").click()
    judge_watches()
    consume_browser_errors(page, {"code": "place-resized", "place": ["div#row"]})


def test_an_occupant_that_fills_its_place_passes(browser):
    page = row_page(browser, "replace", tall=False)
    page.locator("#swap").click()
    judge_watches()


def test_an_occupant_its_words_grew_passes(browser):
    """Words are content, which may size a place: a draft grown by its lines gives way
    to the next occupant, though Send emptied it in that frame."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><div id="row" style="display:flex;width:300px">'
            '<textarea id="draft" rows="1" style="height:24px"></textarea>'
            '<button id="next" style="height:24px" hidden>Next</button></div>'
            "<script>"
            "draft.addEventListener('input', () => { draft.style.height = '60px'; });"
            "draft.addEventListener('keydown', (event) => {"
            " if (event.key !== 'Enter') return;"
            " draft.value = ''; draft.hidden = true; next.hidden = false; });"
            "</script>"
        )
    )
    page.locator("#draft").press_sequentially("Two lines")
    # The grown draft is laid out in a frame of its own, as a user's typing is.
    one_frame(page)
    page.keyboard.press("Enter")
    judge_watches()


def test_a_swap_its_own_press_undoes_before_a_frame_passes(browser):
    """A press's mouse and touch events run in its pointerdown's task, before any frame,
    so a swap one of them undoes was never on screen."""
    page = row_page(browser, "none", tall=False)
    page.evaluate("""() => {
      const [first, second] = ['first', 'second'].map(id => document.getElementById(id));
      second.style.height = '40px';
      addEventListener('pointerdown', () => { first.hidden = true; second.hidden = false; });
      addEventListener('mousedown', () => { first.hidden = false; second.hidden = true; });
    }""")
    page.locator("#swap").click()
    judge_watches()


@pytest.mark.parametrize("tree", ["light", "shadow"])
def test_a_row_a_neighbour_grows_as_its_seat_changes_hands_passes(browser, tree):
    """A field beside the swap that takes more lines in the same press sizes the row,
    not the occupant that arrived, whether the row lays out its own children or a
    shadow tree's."""
    seats = (
        '<textarea id="field" style="height:24px"></textarea>'
        '<button id="short" style="height:24px">Short</button>'
        '<button id="tall" style="height:40px" hidden>Tall</button>'
    )
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><div id="row" style="display:flex;width:300px"></div>'
            "<button id=swap>Swap</button><script>"
            f"const seats = {seats!r};"
            "const tree = "
            + ("row.attachShadow({mode: 'open'});" if tree == "shadow" else "row;")
            + "tree.innerHTML = seats;"
            "const seat = id => tree.querySelector('#' + id);"
            "swap.addEventListener('click', () => { seat('field').style.height = '60px';"
            " seat('short').hidden = true; seat('tall').hidden = false; });"
            "</script>"
        )
    )
    page.locator("#swap").click()
    judge_watches()


def test_a_row_reordered_as_it_loses_its_tallest_passes(browser):
    """A row that loses an item while a keyed renderer moves another within it changed
    its content; the moved item took no one's seat."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><div id="row" style="display:flex;width:300px">'
            '<button id="tall" style="height:40px">Tall</button>'
            "<button id=moved>Moved</button><button>Stays</button></div>"
            "<button id=swap>Swap</button><script>"
            "swap.addEventListener('click', () => { tall.remove(); row.append(moved); });"
            "</script>"
        )
    )
    page.locator("#swap").click()
    judge_watches()


def test_a_wrapping_list_grows_for_its_lines_of_controls(browser):
    """Several lines of choices occupy more room than the one-line result they replace;
    that is a list changing its content, not a control sizing a shared line."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><div id="row" style="display:flex;flex-wrap:wrap;'
            'align-items:center;width:300px;gap:6px;padding-top:9px">'
            '<span style="height:28px">Answered</span></div>'
            '<button id="swap">Change answer</button><script>'
            "const result = row.innerHTML;"
            "swap.addEventListener('click', () => { row.innerHTML = row.children.length === 1 ? "
            "'<button style=\"height:40px;flex:1 0 100%\">First choice</button>' + "
            "'<button style=\"height:40px;flex:1 0 100%\">Second choice</button>' : result; });"
            "</script>"
        )
    )
    for height in (95, 37):
        page.locator("#swap").click()
        assert page.locator("#row").bounding_box()["height"] == height
        judge_watches()
