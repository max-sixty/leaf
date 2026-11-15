"""The browser fixture fails what the "Shared containers determine control dimensions" rule
forbids (`swap_watch.js`): a place that changes size as one occupant gives way to
another."""

from urllib.parse import quote

import pytest
from render_harness import (
    consume_browser_errors,
    judge_watches,
    reported_browser_errors,
)

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


# A row stands at 24px for a few frames; then a page observer watching the deep box
# swaps its occupant for a 40px one inside its delivery.
SWAPPED_IN_DELIVERY = """() => new Promise((done) => {
  holder.innerHTML = '<div id="row" style="display:flex;width:300px">'
    + '<button id="first" style="height:24px">First</button></div>';
  const frames = (n, then) => n ? requestAnimationFrame(() => frames(n - 1, then)) : then();
  frames(4, () => {
    let swapped = false;
    new ResizeObserver(() => {
      if (swapped) return;
      swapped = true;
      const second = document.createElement('button');
      Object.assign(second, {id: 'second', textContent: 'Second'});
      second.style.height = '40px';
      first.replaceWith(second);
    }).observe(deep);
    frames(4, done);
  });
})"""
GREW = {
    "code": "place-resized",
    "place": ["div#row"],
    "left": [["button#first"]],
    "arrived": [["button#second"]],
    "before": {"width": 300, "height": 24},
    "after": {"width": 300, "height": 40},
}


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_standing_row_a_page_observer_swaps_is_judged_without_disturbing_it(
    engine, request
):
    """A page observer on a deep box may change a shallower row inside its delivery,
    which is valid while nothing on the page observes the row's size. The watch neither
    turns that into a loop error nor misses the swap that grew the row."""
    page = request.getfixturevalue(engine).new_page()
    page.goto("data:text/html," + quote(DEEP))
    one_frame(page)
    page.evaluate(SWAPPED_IN_DELIVERY)
    judge_watches()
    consume_browser_errors(page, GREW)


# `mid` stands between the row and the deep box. In the frame a swap grows the row, a
# page observer of the deep box resizes `mid`, which another page observer watches: the
# browser delivers no box as shallow as `mid` after one as deep as the deep box, and
# raises a loop error.
UNDELIVERED = """() => new Promise((done) => {
  const frames = (n, then) => n ? requestAnimationFrame(() => frames(n - 1, then)) : then();
  let started = false;
  new ResizeObserver(() => { if (started) mid.style.height = '20px'; }).observe(deep);
  new ResizeObserver(() => {}).observe(mid);
  frames(4, () => requestAnimationFrame(() => {
    started = true;
    deep.style.height = '20px';
    const second = document.createElement('button');
    Object.assign(second, {id: 'second', textContent: 'Second'});
    second.style.height = '40px';
    first.replaceWith(second);
    frames(4, done);
  }));
})"""


def test_a_loop_error_the_page_raises_reaches_the_test(browser):
    """The watch reads boxes outside the browser's ResizeObserver loop, so it doesn't
    let a page observer deliver where the browser would otherwise leave it undelivered,
    and the loop error the page raises reaches the test beside the swap's finding."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0"><div id="holder">'
            '<div id="row" style="display:flex;width:300px">'
            '<button id="first" style="height:24px">First</button></div></div>'
            '<div><div><div id="mid" style="height:10px"><div><div>'
            '<div id="deep" style="width:10px;height:10px"></div>'
            "</div></div></div></div></div>"
        )
    )
    page.evaluate(UNDELIVERED)
    judge_watches()
    reported_browser_errors(page, "ResizeObserver loop completed", GREW)


def test_a_swap_a_selector_makes_as_the_pointer_arrives_fails(browser):
    """Occupants that trade places under `:hover` change the row with no DOM write;
    the pointer arriving over it is what the watch reads the row after."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            "<!doctype html><style>#second{display:none}"
            "#row:hover #first{display:none}#row:hover #second{display:block}</style>"
            '<body style="margin:0"><div id="row" style="display:flex;width:300px">'
            '<button id="first" style="height:24px">First</button>'
            '<button id="second" style="height:40px">Second</button></div>'
        )
    )
    page.mouse.move(600, 600)
    one_frame(page)
    page.mouse.move(10, 10)
    judge_watches()
    consume_browser_errors(page, GREW)


# A row standing on its own with `first` as its occupant, and the swap that gives its
# seat to a 40px `second`.
STILL_ROW = (
    '<!doctype html><body style="margin:0"><div id="row" style="display:flex;width:300px">'
    "{first}</div>"
)
SWAP_IN_SECOND = """() => new Promise((done) => {
  const second = document.createElement('button');
  Object.assign(second, {id: 'second', textContent: 'Second'});
  second.style.height = '40px';
  first.replaceWith(second);
  requestAnimationFrame(() => requestAnimationFrame(done));
})"""


def test_a_row_an_arriving_image_grew_keeps_its_size_through_a_swap(browser):
    """The image arriving is read as the row's new size, so the swap that follows is
    judged against the row the user saw, which it doesn't change."""
    page = browser.new_page()
    held = []
    page.route("**/picture.svg", lambda route: held.append(route))
    page.goto(
        "data:text/html,"
        + quote(
            STILL_ROW.format(
                first='<div id="first" style="min-height:24px"><img id="picture"'
                ' style="display:block;width:40px" src="http://swap.test/picture.svg">'
                "</div>"
            )
        ),
        wait_until="domcontentloaded",
    )
    one_frame(page)
    assert held, "the image's request is held"
    held[0].fulfill(
        content_type="image/svg+xml",
        body='<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"></svg>',
    )
    page.wait_for_function("picture.complete && picture.naturalHeight === 40")
    one_frame(page)
    page.evaluate(SWAP_IN_SECOND)
    judge_watches()


def test_a_row_a_transition_grew_keeps_its_size_through_a_swap(browser):
    """Each frame of a transition is read, so the swap after it is judged against the
    height it ended at."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            STILL_ROW.format(first='<button id="first">First</button>').replace(
                "<body",
                "<style>#first{height:24px;transition:height .2s linear}"
                "#first.tall{height:40px}</style><body",
            )
        )
    )
    one_frame(page)
    page.evaluate("first.classList.add('tall')")
    page.wait_for_function("!first.getAnimations().length")
    one_frame(page)
    page.evaluate(SWAP_IN_SECOND)
    judge_watches()


def test_a_row_a_text_write_grew_keeps_its_size_through_a_swap(browser):
    """New words in a text node, as Lit writes a binding, grow an occupant with no
    element written. The row is read after them, so the swap that follows is judged
    against the row the user saw."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            STILL_ROW.format(
                first='<div id="first" style="width:40px;font:13px/16px monospace;'
                'padding:4px 0">a</div>'
            )
        )
    )
    one_frame(page)
    page.evaluate("first.firstChild.data = 'aaaa aaaa'")
    assert page.evaluate("first.offsetHeight") == 40, "the words take two lines"
    one_frame(page)
    page.evaluate(SWAP_IN_SECOND)
    judge_watches()


def test_an_occupant_moved_on_before_a_frame_takes_no_seat(browser):
    """An element that arrives in a row and moves elsewhere before the next frame was
    never painted there. The row lost an occupant and grew for one that stood through
    the change, which is no swap."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0">'
            '<div id="row" style="display:flex;align-items:flex-start;width:300px">'
            '<div id="keep" style="width:40px;height:20px"></div>'
            '<button id="first" style="height:24px">First</button></div>'
            '<div id="elsewhere"></div>'
        )
    )
    one_frame(page)
    page.evaluate("""async () => {
      const big = document.createElement('button');
      big.style.height = '40px';
      row.append(big);
      first.remove();
      keep.style.height = '30px';
      await null;
      elsewhere.append(big);
      await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
    }""")
    judge_watches()


def test_a_row_grown_under_a_transform_is_judged_in_layout_pixels(browser):
    """A row drawn at twice its size grows with its occupant like any other: the watch
    reads its boxes in layout pixels, which a transform doesn't change, as its padding
    is."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0">'
            '<div style="transform:scale(2);transform-origin:top left">'
            '<div id="row" style="display:flex;align-items:center;padding:10px 0;'
            'width:300px"><button id="first" style="height:24px">First</button>'
            "</div></div>"
        )
    )
    one_frame(page)
    page.evaluate(SWAP_IN_SECOND)
    judge_watches()
    consume_browser_errors(
        page,
        {
            **GREW,
            "before": {"width": 300, "height": 44},
            "after": {"width": 300, "height": 60},
        },
    )


def test_an_occupant_shown_for_one_frame_is_judged_in_that_frame(browser):
    """A frame paints a taller occupant that a page IntersectionObserver, delivering
    after that paint, puts back. The row grew and shrank on screen, and both are judged
    from the boxes that frame painted, not the page as it stands when they are read."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            STILL_ROW.format(
                first='<button id="first" style="height:24px">First</button>'
            )
        )
    )
    one_frame(page)
    page.evaluate("""() => new Promise((done) => requestAnimationFrame(() => {
      const second = document.createElement('button');
      Object.assign(second, {id: 'second', textContent: 'Second'});
      second.style.height = '40px';
      first.replaceWith(second);
      new IntersectionObserver((entries, observer) => {
        observer.disconnect();
        const third = document.createElement('button');
        Object.assign(third, {id: 'third', textContent: 'Third'});
        third.style.height = '24px';
        second.replaceWith(third);
        requestAnimationFrame(() => requestAnimationFrame(done));
      }).observe(second);
    }))""")
    judge_watches()
    reported_browser_errors(
        page,
        GREW,
        {
            **GREW,
            "left": [["button#second"]],
            "arrived": [["button#third"]],
            "before": {"width": 300, "height": 40},
            "after": {"width": 300, "height": 24},
        },
    )


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
