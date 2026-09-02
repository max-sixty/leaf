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
handed over: the exact current source loads in the host's browser (whichever
executable `LEAF_BROWSER_EXECUTABLE`, `CHROME_PATH`, or `CHROME_BIN` names, else
Playwright's `channel="chrome"`, else the first browser `PATH` answers with — the
caller supplies playwright, which
`bin/leaf` does on seeing `--render`) and the render invariants the static lint cannot reach run
against it — no console or page errors, no fail-soft error box, every visible
widget occupies real space, code that reads against the block it is set on, no
sideways scroll, in both color schemes.
The invariants live in render_version, which the tests/test_render_*.py modules drive over
the shipped examples. The suite uses Chromium's headless shell, while its
end-to-end render-check tests run the launches used here — the installed Chrome
channel, and the headless shell handed over under each variable that names one —
and a unit reading covers the PATH search, which is only reached where the channel
misses. `version export` launches through the same helper, so the two move together.

The one thing export asks of a browser that the render gate does not is its age. The
copy ends in `root.getHTML({ serializableShadowRoots: true })`, which Chromium grew
in 125, so a browser older than that draws every render invariant clean and then
cannot be copied from. `version export` reads `browser.version` before it opens the
page and refuses below the floor by name, rather than letting the bake fail inside
the probe and report a probe module it could not load.

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
The event door repeats that semantic check under the append transaction, but only
for a transport that reaches it with nothing resolved — the MCP app, which renders
the authored source with no runtime behind it. A runtime's own anchor is already
answered against the rendered page, which holds words this reading cannot produce —
a widget's label, a module's rendering — so re-reading it off the file would refuse a
passage the page shows. Whitespace is the other refusal, and it is not the
current runtime's doing: `quoteFrom` in assets/runtime/passages.js collapses a live
selection to the same class this reading does, spelled to passages.py's
COLLAPSE_CHARS, so those two agree. The spellings that arrive uncollapsed are the
ones earlier runtimes write — test_a_quote_finds_its_passage_whatever_its_whitespace
names them — and they name the same words, so a comparison against the canonical
quote would turn a passage down for its whitespace alone.
Where the capture does run, a transport may omit optional context for a quote that
is unique in its declared section; when a quote repeats, its supplied prefix and
suffix must resolve exactly one current occurrence. Widget source, retired text,
and unresolved ambiguous passages are refused before append.

## Parsed source

A page source is written in more than one language, and each language is read by a
parser for that language: _StructParser for what the markup declares,
page_passages for what it says, tinycss2 for the CSS a <style> block holds. A
new question about a page becomes a field on one of those readings rather
than a pattern over the file's text, because a pattern answers something
adjacent to the question asked — `leaf.styles._overwide_elements`
carries the evidence of that cost.
