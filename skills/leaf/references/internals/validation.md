# Validation contract

## Static validation

`version check` is a deterministic check of the exact mutable `index.html` (no
browser, near-free; activation and `version stamp` run the same boundary): the HTML parses with balanced
tags; one direct `<body><main>` contains all authored content; the page carries
exactly one external script
(<script type="module" src="/leaf.js">) and one stylesheet link
(/theme.css), both directly in `<head>` so the presentation boundary exists before
body paint; every lf-* element validates against the vendored registry
(schema, nesting, no self-closing form); every lf-* meta is a known page
declaration with an allowed value; each lf-suggestion is well formed (at most
one of each slot, at least one of them, no nesting, `resolves` naming a real
comment); ids are unique, and ids needed by unresolved threads, standing reader
actions, or effective standing reports survive from the previous revision. A
declared retirement protects its holder and slots until its outcome licenses
their removal. Other dropped ids are reported as advice. No fixed-pixel-width
element is wider than the readable column (the rule that draws that column claims
it with `--lf-column: 1`, so the width and the claim come from one block). Near-free
and deterministic is what makes running it on every save affordable, so keep a new
check that way; anything needing a browser belongs in `--render`.

## Browser validation

`version check --render` adds the browser half, run once before a page's URL is first
handed over: the exact current source loads in the machine's installed Chrome (Playwright
`channel="chrome"` — the caller supplies playwright, which `bin/leaf` does
on seeing `--render`) and the render invariants the static lint cannot reach run
against it — no console or page errors, no fail-soft error box, every visible
widget occupies real space, code that reads against the block it is set on, no
sideways scroll, in both color schemes.
The invariants live in render_version, which the tests/test_render_*.py modules drive over
the shipped examples. The suite uses Chromium's headless shell, while its
end-to-end render-check tests cover the installed Chrome launch used here.

## Passages

An anchor is resolved in the browser and recorded in the event log, so
`leaf comment` reads the active revision the way the anchor pass reads the DOM — text in
document order, minus the runtime's own words, plus the words a widget says
through an x-says attribute, with one space wherever the enclosing text block
changes and whitespace collapsed. What the file cannot know is what a widget's
module will write, so the reading stops where the registry stops telling it: an
upgraded element is opaque unless x-verbatim says its body reaches the reader as
its own words, and an opaque element and each of its children is fenced. A quote
never spans a fence, so "the page has words here that the file doesn't" becomes
a refusal when the comment is written, rather than an anchor that detaches later
in the user's browser. Anchor on an opaque widget's element instead
(`--section`), which is the same anchor a click on a diagram makes.
The browser event door repeats that semantic check for page and passage comment
anchors under the append transaction. A transport may omit optional context for
a quote that is unique in its declared section; when a quote repeats, its supplied
prefix and suffix must resolve exactly one current occurrence. Widget source,
retired text, and unresolved ambiguous passages are refused before append.

## Parsed source

A page source is written in more than one language, and each language is read by a
parser for that language: _StructParser for what the markup declares,
page_passages for what it says, tinycss2 for the CSS a <style> block holds. A
new question about a page becomes a field on one of those readings rather
than a pattern over the file's text, because a pattern answers something
adjacent to the question asked — `leaf.styles._overwide_elements`
carries the evidence of that cost.
