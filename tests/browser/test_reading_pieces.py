"""The page's reading kept in pieces (passages.js, `Piece`), where a browser's answer
decides it: which slot shows a host's child, since a browser assigns a child to one slot
where the runtime tests' DOM assigns it to every slot that would take it, and which
words a search can reach, which it reads off computed styles."""

import pytest
from render_cases_interaction import live_url
from render_harness import open_page

# The test stages content into the page by script, which moves what follows it.
pytestmark = pytest.mark.shifts_unsurveyed

PAGE = """<!doctype html>
<html lang="en"><head><title>Reading pieces</title></head>
<body><main><h1>Reading pieces</h1><p id="outro">The outro closes the page.</p></main>
</body></html>"""

# Stages a declared tree of two parts before the outro, one slot in each part or only in
# the second, gives the host a child, makes `change`, and returns the words after the
# title as the kept reading has them and as a fresh reading has them.
SLOT_MOVE = """async ([first, change]) => {
  const entry = new URL(document.querySelector("script[data-lf-entry]").dataset.lfEntry, location.href);
  const P = await import(new URL("runtime/passages.js", entry).href);
  const { registry } = await import(new URL("runtime/registry.js", entry).href);
  const { shadowStage } = await import(new URL("runtime/shadow-stage.js", entry).href);
  let generation = 0;
  const fresh = () => {
    registry["lf-staged"] = { "x-shadow": true };
    registry.$layer = { ...registry.$layer, generation: `pieces-${(generation += 1)}` };
  };
  const datum = (id, inner) =>
    `<div id="${id}" data-lf-projection="w" data-lf-datum="${id}">${inner}</div>`;
  fresh();
  const host = document.createElement("lf-staged");
  document.querySelector("#outro").before(host);
  const template = document.createElement("template");
  template.innerHTML = datum("ps", `<p id="sp">Staged ${first}</p>`) + datum("pt", "<p><slot></slot></p>");
  shadowStage(host, [...template.content.childNodes]);
  host.innerHTML = "<i>Other</i>";
  for (const root of P.readingParts()) P.pageText(root);
  const sp = host.shadowRoot.getElementById("sp");
  if (change === "add") sp.append(document.createElement("slot"));
  else sp.querySelector("slot").remove();
  const words = () => P.readingParts().map((root) => P.pageText(root).raw.replace(/\\u0000/g, "|"));
  const kept = words();
  fresh();
  return { kept, fresh: words() };
}"""


@pytest.mark.parametrize(
    ("first", "change"),
    [("", "add"), ("<slot></slot>", "remove")],
    ids=["a slot put in one part", "a slot taken out of one part"],
)
def test_a_slot_moving_a_child_between_parts_changes_both(
    browser, serve, first, change
):
    page = open_page(browser, live_url(serve(PAGE)))
    words = page.evaluate(SLOT_MOVE, [first, change])
    assert words["kept"] == words["fresh"]


# A search over prose and two parts, by the page's own passages module: the words of each
# match as it is taken, and whether the second part had been read by then, which asks
# each element inside it where it stands.
FIND = """async () => {
  const entry = new URL(document.querySelector("script[data-lf-entry]").dataset.lfEntry, location.href);
  const P = await import(new URL("runtime/passages.js", entry).href);
  const datum = (id, inner) =>
    `<div id="${id}" data-lf-projection="w" data-lf-datum="${id}">${inner}</div>`;
  const box = document.createElement("section");
  box.innerHTML = "<p>needle in the intro</p>" + datum("a", "<p>a needle in a</p>") +
    "<p>needle between</p>" + datum("b", "<p>b needle in b</p><p>needle again in b</p>") +
    "<p>last needle</p>";
  document.querySelector("#outro").before(box);
  const b = document.getElementById("b");
  const { matches } = Element.prototype;
  let asked = 0;
  Element.prototype.matches = function (selector) {
    if (this !== b && b.contains(this)) asked += 1;
    return matches.call(this, selector);
  };
  const taken = [];
  try {
    for (const match of P.pageMatches("needle"))
      if (match) taken.push([match[0].node.data, asked > 0]);
    return taken;
  } finally {
    Element.prototype.matches = matches;
  }
}"""


def test_a_search_finds_each_match_in_prose_and_every_part_in_reading_order(
    browser, serve
):
    """A search reads a part only once it reaches it, so whoever takes its matches a few at
    a time reads no part ahead of them."""
    page = open_page(browser, live_url(serve(PAGE)))
    assert page.evaluate(FIND) == [
        ["needle in the intro", False],
        ["a needle in a", False],
        ["needle between", False],
        ["b needle in b", True],
        ["needle again in b", True],
        ["last needle", True],
    ]
