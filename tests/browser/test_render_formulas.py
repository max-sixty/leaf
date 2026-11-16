"""A formula's LaTeX, typeset as MathML the browser draws, reads as its source."""

from model_folds import leaf_page
from render_harness import consume_browser_errors, open_page

from leaf import anchor_capture as anchor_capture_model
from leaf import passages as passages_model
from leaf import structure as structure_model

FORMULAS = leaf_page(
    "Formulas",
    '<h1>Cost</h1><p id="cost">Each request costs <code class="language-math">'
    "c(x) = h x + c_0</code> cached reads, over the run.</p>"
    '<pre id="objective"><code class="language-math">'
    "J(X) = \\frac{\\int_K^X c(x)\\,dx}{X - K}</code></pre>",
)

# The words a drag from one of the paragraph's words to another selects, as the page's
# comment capture reads the selection (native-selection.js, `pageRange`).
DRAGGED = """async () => {
  const entry = new URL(document.querySelector("script[data-lf-entry]").dataset.lfEntry, location.href);
  const { anchorForRange } = await import(new URL("runtime/anchor-resolution.js", entry).href);
  const { pageRange } = await import(new URL("runtime/native-selection.js", entry).href);
  return anchorForRange(pageRange(getSelection()));
}"""

# Where a passage that is one whole formula is drawn: its words have no lines of their
# own (passages.js, `drawnLines`).
DRAWN = """async (anchor) => {
  const entry = new URL(document.querySelector("script[data-lf-entry]").dataset.lfEntry, location.href);
  const { resolveAnchor } = await import(new URL("runtime/anchor-resolution.js", entry).href);
  const { passageBoxes } = await import(new URL("runtime/resolved-target.js", entry).href);
  const math = document.querySelector("#cost [data-lf-formula]").shadowRoot.querySelector("math");
  const drawn = math.getBoundingClientRect();
  return passageBoxes(resolveAnchor(anchor)).map((box) =>
    box.left >= drawn.left - 1 && box.right <= drawn.right + 1 && box.height > 0);
}"""

WORD = """([word]) => {
  const p = document.getElementById("cost");
  for (const node of p.childNodes) {
    const at = node.nodeType === Node.TEXT_NODE ? node.data.indexOf(word) : -1;
    if (at < 0) continue;
    const range = document.createRange();
    range.setStart(node, at);
    range.setEnd(node, at + word.length);
    const box = range.getBoundingClientRect();
    return {x: box.x, right: box.right, y: box.y + box.height / 2};
  }
}"""


def test_a_formula_is_drawn_as_mathml_and_quoted_by_its_latex(browser, serve):
    """The reader sees MathML, inline in its sentence and on a line of its own in a
    `<pre>`, while the page's reading keeps the LaTeX the file holds: a drag across an
    inline formula quotes its source, and the file resolves that quote, so a comment
    across a formula neither detaches nor names words the author can't find. A drag
    that ends inside a formula takes all of it, where Chromium's legacy Range stopped
    before it, and Firefox's held only the words after a formula it crossed."""
    page = open_page(browser, serve(FORMULAS))
    drawn = page.evaluate(
        """() => [...document.querySelectorAll("code.language-math")].map((code) => {
          const math = code.querySelector("[data-lf-formula]")?.shadowRoot?.querySelector("math");
          return math && {display: math.getAttribute("display"), height: math.getBoundingClientRect().height};
        })"""
    )
    assert [formula and formula["display"] for formula in drawn] == [None, "block"]
    assert all(formula["height"] > 0 for formula in drawn)

    start = page.evaluate(WORD, ["costs"])
    formula = page.locator("#cost code").bounding_box()
    end = page.evaluate(WORD, ["cached"])
    passages = passages_model.page_passages(structure_model.SourceDocument(FORMULAS))
    for x, quote in [
        (formula["x"] + formula["width"] / 2, "costs c(x) = h x + c_0"),
        (end["right"] - 1, "costs c(x) = h x + c_0 cached"),
    ]:
        page.evaluate("getSelection().removeAllRanges()")
        page.mouse.move(start["x"] + 1, start["y"])
        page.mouse.down()
        page.mouse.move(x, start["y"], steps=8)
        page.mouse.up()
        anchor = page.evaluate(DRAGGED)
        assert anchor["quote"] == quote
        assert anchor_capture_model.resolve_quote(passages, anchor) is not None
    # A comment on the formula alone stands where the formula is drawn.
    assert page.evaluate(DRAWN, {"section": "cost", "quote": "c(x) = h x + c_0"}) == [
        True
    ]


def test_a_formula_temml_refuses_keeps_its_source_and_says_why(browser, serve):
    """The author's mistake reaches the page's log, where `page check --render` and
    the agent read it, and the reader keeps the source rather than a blank."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Refused formula",
                '<p id="broken">Half of <code class="language-math">\\frac{a}{</code>.</p>',
            )
        ),
    )
    consume_browser_errors(page, "Unexpected end of input")
    assert page.locator("#broken code").text_content() == "\\frac{a}{"
    assert page.locator("#broken [data-lf-formula]").count() == 0
