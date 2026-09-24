# Validation contract

## Event admission

Every writer uses the shared append transaction described in
[events.md, "Admission"](events.md#admission). `page init` also checks the
standing log against the replacement layer's stored-record contracts before
re-vendoring.

## Static validation

`version check` is a deterministic check of the exact mutable `index.html` (no
browser, near-free; activation and `version stamp` run the same boundary): the HTML parses with balanced
tags; one direct `<body><main>` contains all authored content; page-authored behavior
appears only in inline modules or literal local module graphs rooted below `/page/`,
never classic scripts, network imports, event-handler attributes, or `javascript:` URLs;
page-specific presentation appears inline or in captured `/page/` stylesheets. The
encoding, CSP, runtime, theme, page identity, and canonical address belong to delivery
and are rejected in source. Delivery inserts them at the start of `<head>`, before
authored executable content, and marks each authored inline module with the nonce its
policy names. Every lf-* element validates against the effective registry
(schema, nesting, no self-closing form); every lf-* meta is a known page
declaration with an allowed value; each lf-suggestion is well formed (at most
one of each slot, at least one of them, no nesting, `resolves` naming a comment
in the document's reference namespace); ids are unique, no authored id, class, or
attribute sits in the runtime's `lf-` and `data-lf-` namespaces, named today or
not, and ids needed by anchored unresolved threads, standing user actions, or
effective standing reports survive from the previous revision. A
declared visual part survives on the same terms as an id: while a live
conversation's current anchor names it, and no longer once every thread on it
has moved, detached, or closed. That release is final — a revision the part has
left cannot be asked for it back, so reopening the closed conversation restores
the thread and not its target. An agent reply may detach a thread in the same
transition that removes its subject. A declared retirement protects its holder and slots until its
outcome licenses their removal. Other dropped ids are reported as advice. No fixed-pixel-width
element is wider than the readable column (the rule that draws that column claims
it with `--lf-reading-column: 1`, so the width and the claim come from one block). Near-free
and deterministic is what makes running it on every save affordable, so keep a new
check that way; anything needing a browser belongs in `--render`.

An ordinary document's comment namespace is the roots present in its log. A
specimen template's namespace is its `data-specimen-threads` declaration, so a
first version may name conversations whose seed log has not been written yet.
Static validation applies the same child-document checks using the selected
history currently available. Specimen allocation copies that same available
history and no more, so a root the log does not hold leaves the child without
that conversation rather than refusing the page. Corpus generation selects
against the shipped log it is composing from, where a root naming nothing is a
mistake in the declaration, and refuses it.

## Delivery policy

The document policy cannot restrict ancestors when delivered through `<meta>`. Every
ordinary served HTML response therefore adds `frame-ancestors 'none'`. Historical
version routes receive the current document policy and the same header. A standalone
file has no response header and cannot make this framing guarantee. The process-scoped
MCP page server omits the header because its exact, ephemeral origin is intentionally
framed by the host that approved it; the unguessable page path remains that transport's
access boundary. A specimen child permits its same-origin parent with
`frame-ancestors 'self'`; under the MCP transport it inherits the omitted header,
so the host can frame the complete page hierarchy. Every response carries
`X-Content-Type-Options: nosniff`; typed data is available only through its JSON
API, and media routes serve only admitted image types, so neither input surface
can become a script module.

## Browser validation

`version check --render` adds the browser half, run once before a page's URL is first
handed over: the exact current source loads in the host's browser (whichever
executable `LEAF_BROWSER_EXECUTABLE`, `CHROME_PATH`, or `CHROME_BIN` names, else
Playwright's `channel="chrome"`, else the first browser `PATH` answers with) and the
render invariants the static lint cannot reach run against it in both color schemes:
no console or page errors and no fail-soft box; every widget upgraded, painted with
values that resolve, and given real space; words a user can mark, reach, and
select, with the registry's verbatim and shadow declarations honored; no sideways
scroll, clipped control, squeezed table, trapped margin, or misplaced box; a print
rendering that covers and drops nothing; and standing state that replays without
conflict and idempotently. `render_gate/readings.py` is the list. Those readings run
at a desktop and a phone viewport; once they are done, the loaded desktop page is
resized through the widths from 360px to 1200px and the two sideways readings are taken
again at each, because a layout can break only between the viewports, and each fault
found only there is reported at the narrowest width it appears. The gate also gives
advice, which never refuses a version: at the desktop viewport, a page whose layout
grids split at more places than its busiest grid needs is told to lay a sheet on one
set of tracks.
The invariants live in render_version, which the tests/test_render_*.py modules drive over
the shipped examples. The suite uses Chromium's headless shell, while its
end-to-end render-check tests run the launches used here — the installed Chrome
channel, and the headless shell handed over under each variable that names one —
and a unit reading covers the PATH search, which is only reached where the channel
misses. `version export` launches through the same helper, so the two move together.
Playwright's driver runs under its bundled Node, or `PLAYWRIGHT_NODEJS_PATH` when
set. Driver startup failures report the cause, the Node executable, and that
variable; `render_gate/browser.py` owns browser and driver launch diagnostics.

The browser's authored-state conflict check considers only surviving user actions
made before the revision being checked. Actions made on that revision already saw
its markup. After the observational probes, the complete-state renderer shows the
authored baseline and the carried decisions, then restores current state. The gate
reports only individual attributes or placement facts changed both by the author
and by those carried decisions; another verb on the same element is independent.
The runtime keeps no event-to-DOM write history for this check.

Both gates serve their probe modules from the Leaf running the command and the
runtime those modules import from the page, so the ephemeral server they open refuses
a page whose recorded `$layer.runtime` is not the identity this payload's kernel
runtime carries. The kernel is read for that comparison rather than the whole layer,
because it is the half the probe modules import and the only half a payload can
identify anywhere: `$layer.packages` was resolved against the project `page init` ran
in. Without that reading the mismatch arrives as a missing export in the probe module,
which reads as a defect in the page. The vendored layer is the page's to keep, so
neither gate re-vendors on its behalf.

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
module will write, so the reading stops where the registry stops telling it. An
upgraded element is opaque unless x-verbatim promises that its own authored words and
the order and identity of nested upgraded widgets survive. Those descendants retain
their own word and fence contracts; an opaque element and each of its children is
fenced. A quote never spans a fence, so "the page has words here that the file doesn't"
becomes a refusal when the comment is written, rather than an anchor that detaches
later in the user's browser. Anchor on an opaque widget's element instead
(`--section`), which is the same anchor an explicit diagram target makes.
The render gate pairs each preserving owner with the file by its source and
document-order occurrence, captured before upgrade. Page markup and each frozen thread
event are separate sources, so this pairing does not require authored ids. It compares
the rendered owner with the same projected passage a user can point at: standing
user body rewrites replace authored words, retired slots contribute none, and
declared generated children join their owner. Reports do not license a body rewrite.
Page expectations stop at the rendered revision; frozen thread markup has no later
authored version and uses the conversation's whole action window.
Event admission repeats file-side capture only when the transport requests it,
as the MCP snapshot does. Runtime anchors are already resolved against rendered
words, including widget labels and module output unavailable to the file reading,
so admission does not recapture them. Browser `quoteFrom` and Python's
`COLLAPSE_CHARS` define matching whitespace collapse. A recaptured quote must
match the canonical quote exactly.
Where the capture does run, a transport may omit optional context for a quote that
is unique in its declared section; when a quote repeats, its supplied prefix and
suffix must resolve exactly one current occurrence. Widget source, retired text,
and unresolved ambiguous passages are refused before append.

## Parsed source

A page source is written in more than one language. TurboHTML's WHATWG tree drives
the one SourceDocument reading of what the markup declares and says;
SourceDocument also retains exact source spans. tinycss2 reads the CSS a <style> block
holds. A new question about a page becomes a field on one of those readings rather
than a pattern over the file's text, because a pattern answers something adjacent to
the question asked — `leaf.styles._overwide_elements` carries the evidence of that
cost.
