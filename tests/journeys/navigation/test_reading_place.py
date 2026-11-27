"""The reader's place while the page glides: a key pressed during one of Leaf's glides
acts where the glide lands."""

import pytest
from render_harness import LONG_PAGE, held_frames, open_page, scroll_settled

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed

# Top and middle links to stand on and Tab between, a thread for `t` and an ask for
# `m`, both below the middle, so every glide carries the middle link away.
PLACES_PAGE = (
    LONG_PAGE.replace(
        "<p id='p1'>Paragraph 1.", "<p id='p1'>Paragraph 1. <a href='#p1'>Top</a>"
    )
    .replace(
        "<p id='p20'>Paragraph 20.", "<p id='p20'>Paragraph 20. <a href='#p20'>Mid</a>"
    )
    .replace(
        "<p id='p50'>",
        '<lf-group id="ask" label="Which route?"><h2 id="ask-h">Which route?</h2><lf-options id="routes">'
        '<lf-option id="left">Take the left route</lf-option>'
        '<lf-option id="right">Take the right route</lf-option>'
        "</lf-options></lf-group><p id='p50'>",
    )
)

# One glide of each kind: the two walks, travel to an edge, and a step.
GLIDES = ("t", "m", "g g", "d")
# Each key reads where the user is: `c` and Tab the focus they stand on, a walk where it
# starts, a step where the reading is, PageDown the browser's own step, and `g` the
# scene its Go-to map labels.
FOLLOWS = ("c", "Tab", "Shift+Tab", "t", "m", "d", "PageDown", "g")

# Cases that end elsewhere pressed during the glide, each a defect to fix rather than a
# rule. An entry that no longer fails fails the test, so a fix takes its entry away.
KNOWN = {
    ("t", "Tab", "at once"): (
        {"chromium"},
        "Chromium reveals the card's next control where the card stood before the walk's "
        "glide landed, since a box the page carries by anchoring takes a scroll at the "
        "next frame (notes/browser-support.md, 'A reveal of an anchored fixed box "
        "before the next frame in Chromium')",
    ),
}

# Where focus stands, named by the Leaf surfaces down to it from the nearest authored
# id, whether the user sees it, and the page's scroll.
OUTCOME = """() => {
  let node = document.activeElement;
  while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
  const path = [];
  for (let at = node; at && at !== document.body; at = at.parentElement ?? at.getRootNode().host) {
    if (at.id && document.getElementById(at.id) === at && !at.closest("[class*=lf-]")) {
      path.push("#" + at.id);
      break;
    }
    const marks = [...at.classList].filter((name) => name.startsWith("lf-"));
    path.push(at.localName + marks.map((name) => "." + name).join(""));
  }
  const box = node?.getBoundingClientRect();
  return {
    focus: path.reverse().join(" "),
    seen: Boolean(box && box.bottom > 0 && box.top < innerHeight),
    top: Math.round(scrollY),
  };
}"""

# The page's scroll as each key arrives, recorded before any of the page's own listeners
# hear it. `__lfLog` keeps each key, scroll, scroll end and focus with its time and the
# page's scroll, and each but a scroll with the focused node's box, so a failure that only
# the macOS nightly shows carries its own sequence in the assertion's message.
AT_EACH_KEY = """globalThis.__lfLog = [];
{
const focused = () => {
  let node = document.activeElement;
  while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
  const box = node?.getBoundingClientRect();
  return `${node?.id || node?.localName}@${Math.round(box?.top)}..${Math.round(box?.bottom)}`;
};
const note = (...entry) =>
  __lfLog.push([...entry, Math.round(performance.now()), Math.round(scrollY)]);
addEventListener("keydown", (event) => {
  globalThis.__lfAtKey = scrollY;
  note("key", event.key, focused());
}, {capture: true});
addEventListener("keydown", (event) =>
  note("handled", event.key, event.defaultPrevented, focused()));
addEventListener("scroll", () => note("scroll"), {capture: true});
for (const kind of ["scrollend", "focusin"]) {
  addEventListener(kind, () => note(kind, focused()), {capture: true});
}
}"""


# Daily, by the user's choice: each case fits the browser tier's budget,
# but together they take minutes of CPU, which each push to main would pay.
@pytest.mark.parametrize("when", ["at once", "under way"])
@pytest.mark.parametrize("follow", FOLLOWS)
@pytest.mark.parametrize("glide", GLIDES)
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_key_pressed_during_a_glide_acts_where_the_glide_lands(
    engine, glide, follow, when, request, serve
):
    """A key pressed while one of Leaf's glides runs acts as it would once the glide had
    landed (readings/user-place.js, `focusPlace`). Every glide here sets off from a link in the
    middle of the page and carries it away, and the key that follows ends the same way
    pressed during the glide as after its landing: focus on the same control, as seen,
    and the page at the same scroll. During it is at once, before the glide's first
    frame, or under way, two frames after the glide first moved the page, which leaves
    it most of the way along, where the destination of a second walk may already be in
    view."""
    browser = request.getfixturevalue(engine)
    engines, reason = KNOWN.get((glide, follow, when), ((), ""))
    if browser.browser_type.name in engines:
        request.applymarker(pytest.mark.xfail(strict=True, reason=reason))

    def run(when):
        page = open_page(
            browser,
            serve(PLACES_PAGE, anchored=[("p41", "Paragraph 41.")]),
            init_script=AT_EACH_KEY,
        )
        page.locator("#p20 a").focus()
        scroll_settled(page)
        rendered(page)
        start = page.evaluate("scrollY")
        with held_frames(page) as step:
            for key in glide.split():
                page.keyboard.press(key)
            if when == "under way":
                for _ in range(30):
                    if page.evaluate("scrollY") != start:
                        break
                    step()
                else:
                    raise AssertionError("the glide never set off")
                step()
                step()
            if when != "after":
                page.keyboard.press(follow)
        if when == "after":
            scroll_settled(page)
            rendered(page)
            page.keyboard.press(follow)
        scroll_settled(page)
        rendered(page)
        return (
            page.evaluate("__lfAtKey"),
            page.evaluate(OUTCOME),
            page.evaluate("__lfLog"),
        )

    landing, settled, after = run("after")
    pressed_at, during, sequence = run(when)
    log = f"\nafter the landing: {after}\nduring the glide: {sequence}"
    assert abs(pressed_at - landing) > 2, "the glide had landed before the key" + log
    assert (during["focus"], during["seen"]) == (settled["focus"], settled["seen"]), log
    assert during["top"] == pytest.approx(settled["top"], abs=2), log
