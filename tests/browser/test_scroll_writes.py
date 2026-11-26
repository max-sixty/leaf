"""A script's scroll write. Through `setScroll`, the runtime's own, it moves a box as far
as the browser lets it, on whichever side of zero the box scrolls, and writes nothing
that would leave a still box where it stands. Through the browser's own calls, whoever
makes it, the runtime hears it as it is made (`runtime/dom/arrivals.js`)."""

import pytest
from render_harness import consume_browser_errors, leaf_page, open_page

from leaf.source.render_checks import SERVED_TIMEOUT_MS

# Each style that decides which side of zero a box scrolls on, alone and in the
# combinations where two of them cancel. Chromium and Firefox agree on every one.
ORIGINS = {
    "plain": "",
    "rtl": "direction: rtl;",
    "row-reverse": "display: flex; flex-direction: row-reverse;",
    "row-reverse-rtl": "display: flex; flex-direction: row-reverse; direction: rtl;",
    "column-reverse": "display: flex; flex-direction: column-reverse;",
    "inline-column-reverse": "display: inline-flex; flex-direction: column-reverse;",
    "wrap-reverse": "display: flex; flex-wrap: wrap-reverse;",
    "column-wrap-reverse": "display: flex; flex-flow: column wrap-reverse;",
    "grid": "display: grid;",
    "vertical-rl": "writing-mode: vertical-rl;",
    "vertical-lr": "writing-mode: vertical-lr;",
    "vertical-rl-rtl": "writing-mode: vertical-rl; direction: rtl;",
    "vertical-lr-rtl": "writing-mode: vertical-lr; direction: rtl;",
    "sideways-lr": "writing-mode: sideways-lr;",
    "sideways-rl": "writing-mode: sideways-rl;",
}

# For each box the selector names, where `setScroll` put it from zero against where the
# browser's own range, read by this test's writes, lets a write past each side go.
MISPLACED = """async (selector) => {
  const {setScroll} = await window.__lfCheckApi();
  const result = {};
  for (const box of document.querySelectorAll(selector)) {
    const name = box.id || box.localName;
    for (const axis of ['top', 'left']) {
      const key = axis === 'top' ? 'scrollTop' : 'scrollLeft';
      box.scrollTo({[axis]: -1e6, behavior: 'instant'});
      const low = box[key];
      box.scrollTo({[axis]: 1e6, behavior: 'instant'});
      const high = box[key];
      for (const to of [-50, 50]) {
        box.scrollTo({[axis]: 0, behavior: 'instant'});
        setScroll(box, {[axis]: to});
        const expected = Math.min(Math.max(to, low), high);
        if (box[key] !== expected)
          result[`${name} ${axis} ${to}`] = {landed: box[key], expected};
      }
    }
  }
  return result;
}"""


def test_a_write_from_zero_moves_a_box_as_far_as_the_browser_lets_it(browser, serve):
    """From rest at zero, a write past either side moves a box to the edge its range
    reaches on that side, or writes nothing where that side is the one it stands at. A
    box scrolls on the negative side where its content flows from the bottom or right
    edge, which nothing but its style shows while it stands at zero: a reversed flex
    column's first move up can be dropped as a write past its top, and a plain box's
    move past its top written though it moves nothing. The write watch fails any write
    that moves nothing (`write_watch.js`)."""
    boxes = "".join(
        f'<div class="origin" id="{name}" '
        f'style="width:200px;height:200px;overflow:auto;{style}">'
        '<div style="width:600px;height:600px;flex:none"></div>'
        '<div style="width:600px;height:600px;flex:none"></div></div>'
        for name, style in ORIGINS.items()
    )
    page = open_page(browser, serve(leaf_page("Scroll origins", boxes)))
    assert page.evaluate(MISPLACED, ".origin") == {}


@pytest.mark.parametrize(
    ("style", "open_axes"),
    [
        ("html { display: flex; flex-direction: column-reverse; }", 0),
        ("body { writing-mode: vertical-rl; }", 1),
    ],
    ids=["root-column-reverse", "body-vertical-rl"],
)
def test_the_page_scrolls_from_the_start_of_its_principal_flow(
    browser, serve, style, open_axes
):
    """The page's own scroll starts where its principal flow does, which no flex flow on
    the root reverses. That flow is the root's or the body's, by rules that turn on
    containment and on which the engines differ, so where the two disagree a write from
    zero is judged against both sides: it is never dropped, and the one past the side
    the page doesn't scroll on moves nothing, as the write watch reports."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Page origin",
                '<div style="width:4000px;height:4000px"></div>',
                head=f"<style>{style}</style>",
            )
        ),
    )
    assert page.evaluate(MISPLACED, "html") == {}
    if open_axes:
        unmoved = consume_browser_errors(page, {"code": "unmoved-scroll"})
        assert len(unmoved) == open_axes, unmoved


# The last thing `box` holds, which stands past its scrollport's end: the page holds it
# in `main`.
HELD = "(box.matches('html') ? document.querySelector('main') : box).lastElementChild"
REVEAL = f"{HELD}.scrollIntoView({{block: 'end', behavior: 'instant'}})"
AWAY = "window.scrollTo({top: 2000, behavior: 'instant'})"

# Each of the browser's own scroll writes, made on `box` from its start, with whether
# it moves the box at once (`placed`), later (`glides`) or not at all (`unmoved`), and
# for a write the page first stands elsewhere for, where (`AWAY`, the boxes at the
# page's start then out of sight).
WRITES = {
    "scrollTo": ("box.scrollTo({top: 120, behavior: 'instant'})", "placed"),
    "scroll": ("box.scroll(0, 120)", "placed"),
    "scrollBy": ("box.scrollBy({top: 120, behavior: 'instant'})", "placed"),
    "scrollTop": ("box.scrollTop = 120", "placed"),
    "scrollLeft": ("box.scrollLeft = 120", "placed"),
    "window.scrollTo": ("window.scrollTo(0, 120)", "placed"),
    "window.scroll": ("window.scroll({top: 120, behavior: 'instant'})", "placed"),
    "window.scrollBy": ("scrollBy(0, 120)", "placed"),
    # A reveal of what the box holds moves the box, and the page too where the box
    # stands out of sight; one of the root moves the page.
    "scrollIntoView": (REVEAL, "placed"),
    "scrollIntoView, box out of sight": (REVEAL, "placed", AWAY),
    "scrollIntoView, of the root": (
        "document.documentElement.scrollIntoView({behavior: 'instant'})",
        "placed",
        AWAY,
    ),
    "restated": ("box.scrollTo({top: 0, behavior: 'instant'})", "unmoved"),
    "smooth": ("box.scrollTo({top: 120, behavior: 'smooth'})", "glides"),
}

SCROLLER = (
    'style="width:200px;height:200px;overflow:auto">'
    '<div style="width:600px;height:1200px"></div></div>'
)

# A scroller in the shadow tree of a component Leaf never staged, whose scroll events
# no listener of Leaf's hears, in a box the page keeps for it.
FOREIGN = f"""() => {{
  document.querySelector('#foreign')
    .attachShadow({{mode: 'open'}}).innerHTML = '<div {SCROLLER}';
}}"""

# What the runtime reads of `write` to the box `selector` names, a path through shadow
# roots: whether a scroll is under way there as the write returns (`heard`), and, where
# the write moves the box, whether the box is the browser's to move at the `scroll`
# event the write sends (`browser`), and the page likewise where the page first stood
# `away` (`page`). Each write starts from a box standing still at its start, in a page
# standing at its own, where the box is in sight, or `away`: the writes that put them
# there are scrolls of their own, which end first.
HEARD = """async ([selector, write, moves, away, deadline]) => {
  const {browserScrolls, scrolling, watchScrollEnds} = await window.__lfCheckApi();
  const box = selector.reduce(
    (root, step) => (root.shadowRoot ?? root).querySelector(step), document);
  const page = document.scrollingElement;
  // Each wait ends at its own event, under a deadline that names the event still
  // missing.
  const within = (what, wait) => Promise.race([
    wait,
    new Promise((_, reject) => setTimeout(
      () => reject(new Error(`no ${what} after ${write} in ${selector.join(' ')}`)),
      deadline)),
  ]);
  for (const moved of [box, page])
    if (moved.scrollTop || moved.scrollLeft)
      moved.scrollTo({top: 0, left: 0, behavior: 'instant'});
  if (away) new Function(away)();
  await within('end of the scrolls before it', new Promise((resolve) => {
    if (!scrolling()) return resolve();
    const stop = watchScrollEnds(() => {
      if (scrolling()) return;
      stop();
      resolve();
    });
  }));
  const scrolled = (moved) => new Promise((resolve) => {
    (moved === page ? document : moved).addEventListener(
      'scroll', () => resolve(browserScrolls(moved)), {once: true});
  });
  const events = [scrolled(box), away ? scrolled(page) : null];
  new Function('box', write)(box);
  const heard = scrolling();
  const [browser, carried] = moves
    ? await within('scroll event', Promise.all(events)) : [null, null];
  return {heard, browser, page: carried};
}"""

# What each of the browser's calls returns to its caller through the hearing, beside
# what it returns in a document nothing wraps, by the kind of value.
RETURNS = """() => {
  const frame = document.createElement('iframe');
  frame.style.cssText =
    'position:fixed;inline-size:0;block-size:0;border:0;visibility:hidden';
  document.body.append(frame);
  const plain = frame.contentDocument.body.appendChild(
    frame.contentDocument.createElement('div'));
  const kind = (value) => Object.prototype.toString.call(value);
  const calls = {
    scrollTo: (box) => box.scrollTo({top: 0, behavior: 'instant'}),
    scrollIntoView: (box) => box.scrollIntoView({block: 'nearest', behavior: 'instant'}),
    'window.scrollTo': (box) => box.ownerDocument.defaultView.scrollTo(0, 0),
  };
  const heard = document.querySelector('#pane');
  const returned = Object.fromEntries(Object.entries(calls).map(
    ([name, call]) => [name, {heard: kind(call(heard)), plain: kind(call(plain))}]));
  frame.remove();
  return returned;
}"""

BOXES = {"box": ["#pane"], "page": ["html"], "foreign": ["#foreign", "div"]}


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_script_s_scroll_write_is_heard_as_it_is_made(request, serve, engine):
    """A write made with one of the browser's own calls, by a package, a page's script or
    a component Leaf never saw, is a script's placement from the call itself: a scroll
    is under way as the call returns, and at the `scroll` event the write sends the box
    stands where a script put it. Heard only at that event, as the browser tells a page
    of a write, the box would read there as the browser's to move. A reveal is such a
    write to each box it moves, the page among them. A write that moves nothing is not
    heard. A smooth one is the browser's to move from its first `scroll` event, where
    the runtime hears the box's events at all: in a shadow tree it never staged it hears
    none, so the box reads as moved by nobody. The caller gets what the browser's call
    returns."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Heard writes",
                f'<div id="pane" {SCROLLER}'
                '<div id="foreign" style="width:200px;height:200px"></div>'
                '<div style="width:4000px;height:3000px"></div>',
            )
        ),
    )
    page.evaluate(FOREIGN)

    def applies(name, how):
        """Whether the write `how` is one for the box `name`: the window's calls and a
        reveal of the root move the page, and only another box stands out of sight."""
        if how.startswith("window.") or how.endswith("of the root"):
            return name == "page"
        return name != "page" or "out of sight" not in how

    read = {
        (name, how): page.evaluate(
            HEARD,
            [
                selector,
                write,
                moves != "unmoved",
                away[0] if away else None,
                SERVED_TIMEOUT_MS,
            ],
        )
        for name, selector in BOXES.items()
        for how, (write, moves, *away) in WRITES.items()
        if applies(name, how)
    }
    assert read == {
        (name, how): {
            "placed": {
                "heard": True,
                "browser": False,
                "page": False if len(WRITES[how]) > 2 else None,
            },
            "unmoved": {"heard": False, "browser": None, "page": None},
            "glides": {"heard": False, "browser": name != "foreign", "page": None},
        }[WRITES[how][1]]
        for name, how in read
    }
    returned = page.evaluate(RETURNS)
    assert all(call["heard"] == call["plain"] for call in returned.values()), returned
