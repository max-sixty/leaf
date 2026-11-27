"""A formula's LaTeX, typeset as MathML the browser draws, reads as its source."""

from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_harness import consume_browser_errors, open_page, select

LONG = " + ".join(f"a_{{{n}}} x^{{{n}}}" for n in range(1, 31))
FORMULAS = leaf_page(
    "Formulas",
    '<h1>Cost</h1><p id="cost">Each request costs <code class="language-math">'
    "c(x) = h x + c_0</code> cached reads, over the run.</p>"
    '<pre id="objective"><code class="language-math">'
    "J(X) = \\frac{\\int_K^X c(x)\\,dx}{X - K}</code></pre>"
    f'<p id="series">The series runs <code class="language-math">{LONG}</code>.</p>',
)

# What the page's comment capture reads of the selection (dom/native-selection.js,
# `pageRange`): the anchor it would quote, or null where the selection is a caret.
SELECTED = """async () => {
  const { anchorForRange, pageRange } = await window.__lfCheckApi();
  const range = pageRange(getSelection());
  return range.collapsed ? null : anchorForRange(range);
}"""

# Where a word of the paragraph stands, for a drag to start or end on.
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
    """The reader sees MathML, inline in its sentence, wrapping where TeX would break a
    long one, and on a line of its own in a `<pre>`, while the page's reading keeps the
    LaTeX the file holds: a drag across an inline formula quotes its source, and the
    file resolves that quote, so a comment across a formula neither detaches nor names
    words the author can't find. A drag that ends inside a formula takes all of it,
    where Chromium's legacy Range stopped before it, and Firefox's held only the words
    after a formula it crossed; a click on one stays a caret, which a range round its
    host would have read as a selection."""
    page = open_page(browser, serve(FORMULAS))
    drawn = page.evaluate(
        """() => [...document.querySelectorAll("code.language-math")].map((code) => {
          const math = code.firstElementChild?.shadowRoot?.querySelector("math");
          return math && {display: math.getAttribute("display"), height: math.getBoundingClientRect().height};
        })"""
    )
    assert [formula and formula["display"] for formula in drawn] == [
        None,
        "block",
        None,
    ]
    assert all(formula["height"] > 0 for formula in drawn)
    assert page.evaluate(
        "() => { const p = document.getElementById('series');"
        " return p.scrollWidth <= p.clientWidth; }"
    )

    start = page.evaluate(WORD, ["costs"])
    formula = page.locator("#cost code").bounding_box()
    end = page.evaluate(WORD, ["cached"])
    for x, quote in [
        (formula["x"] + formula["width"] / 2, "costs c(x) = h x + c_0"),
        (end["right"] - 1, "costs c(x) = h x + c_0 cached"),
    ]:
        page.evaluate("getSelection().removeAllRanges()")
        select(page, (start["x"] + 1, start["y"]), (x, start["y"]))
        anchor = page.evaluate(SELECTED)
        assert anchor["quote"] == quote

    page.evaluate("getSelection().removeAllRanges()")
    page.mouse.click(formula["x"] + formula["width"] / 2, start["y"])
    assert page.evaluate(SELECTED) is None


def test_travel_reaches_a_comment_on_a_formula_alone(browser, serve):
    """A formula's words have no box of their own, so its passage stands at its host's
    edges, where the formula is drawn: travel to a comment quoting one formula brings
    the formula into view, as it does a comment on words."""
    url = serve(
        leaf_page(
            "Formula far down",
            '<h1>Cost</h1><div style="height: 300vh"></div>'
            '<p id="cost">Each request costs <code class="language-math">'
            "c(x) = h x + c_0</code> cached reads.</p>",
        )
    )
    panel_comment(
        serve.page_dir, "Per request?", {"section": "cost", "quote": "c(x) = h x + c_0"}
    )
    page = open_page(browser, url)
    formula = page.locator("#cost code")
    expect(formula).not_to_be_in_viewport()
    page.keyboard.press("t")
    expect(formula).to_be_in_viewport()


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
    code = page.locator("#broken code")
    assert code.evaluate("code => [code.innerHTML, code.dataset.lfFormula]") == [
        "\\frac{a}{",
        None,
    ]
