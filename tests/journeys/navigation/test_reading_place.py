"""The reader's place while the page glides: a key pressed during one of Leaf's glides
acts where the glide lands."""

import pytest
from render_harness import LONG_PAGE, held_frames, open_page, scroll_settled

from leaf.render_checks import rendered

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
        '<lf-ask id="ask"><h2>Which route?</h2><lf-options id="routes" choose>'
        '<lf-option id="left">Take the left route</lf-option>'
        '<lf-option id="right">Take the right route</lf-option>'
        "</lf-options></lf-ask><p id='p50'>",
    )
)

# One glide of each kind: the two walks, travel to an edge, and a step.
GLIDES = ("t", "m", "g g", "d")
# Each key reads where the user is: `c` and Tab the focus they stand on, a walk where it
# starts, and a step where the reading is.
FOLLOWS = ("c", "Tab", "Shift+Tab", "t", "m", "d")

# Pairs that end elsewhere pressed at once, each a defect to fix rather than a rule. An
# entry that no longer fails fails the test, so a fix takes its entry away.
REVEAL = (
    "The reveal of the control Tab reaches, the browser's or Leaf's, reads the page "
    "where the glide has it rather than where it lands, and stops the glide there"
)
KNOWN = {
    ("t", "Tab"): ({"chromium"}, REVEAL),
    ("m", "Tab"): ({"chromium", "firefox"}, REVEAL),
    ("m", "Shift+Tab"): ({"chromium", "firefox"}, REVEAL),
    ("d", "Shift+Tab"): ({"chromium", "firefox"}, REVEAL),
    ("m", "c"): (
        {"chromium", "firefox"},
        "`c` reads whether the ask is seen where the glide has it, so it brings the "
        "ask forward and stops the glide short",
    ),
}
# The same defect where it comes and goes with the frames the page gets: Chromium fails
# it unthrottled and passes it at a tenth of the CPU, and Firefox fails it most runs.
SOMETIMES = {("t", "Shift+Tab"): REVEAL}

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
# hear it.
AT_EACH_KEY = """addEventListener("keydown", () => { globalThis.__lfAtKey = scrollY; },
  {capture: true});"""


# Daily, by the user's choice (2026-11-14): each case fits the browser tier's budget,
# but the 48 together take minutes of CPU, which each push to main would pay.
@pytest.mark.parametrize("follow", FOLLOWS)
@pytest.mark.parametrize("glide", GLIDES)
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_key_pressed_during_a_glide_acts_where_the_glide_lands(
    engine, glide, follow, request, serve
):
    """A key pressed while one of Leaf's glides runs acts as it would once the glide had
    landed (user-place.js, `focusPlace`). Every glide here sets off from a link in the
    middle of the page and carries it away, and the key that follows ends the same way
    pressed at once, before the glide's first frame, as pressed after its landing:
    focus on the same control, as seen, and the page at the same scroll."""
    browser = request.getfixturevalue(engine)
    engines, reason = KNOWN.get((glide, follow), ((), ""))
    if browser.browser_type.name in engines:
        request.applymarker(pytest.mark.xfail(strict=True, reason=reason))
    elif reason := SOMETIMES.get((glide, follow)):
        request.applymarker(pytest.mark.xfail(strict=False, reason=reason))

    def run(at_once):
        page = open_page(
            browser,
            serve(PLACES_PAGE, anchored=[("p41", "Paragraph 41.")]),
            init_script=AT_EACH_KEY,
        )
        page.locator("#p20 a").focus()
        scroll_settled(page)
        rendered(page)
        with held_frames(page):
            for key in glide.split():
                page.keyboard.press(key)
            if at_once:
                page.keyboard.press(follow)
        if not at_once:
            scroll_settled(page)
            rendered(page)
            page.keyboard.press(follow)
        scroll_settled(page)
        rendered(page)
        return page.evaluate("__lfAtKey"), page.evaluate(OUTCOME)

    landing, settled = run(at_once=False)
    pressed_at, at_once = run(at_once=True)
    assert abs(pressed_at - landing) > 2, "the glide had landed before the key"
    assert (at_once["focus"], at_once["seen"]) == (settled["focus"], settled["seen"])
    assert at_once["top"] == pytest.approx(settled["top"], abs=2)
