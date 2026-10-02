# Validation contract

## Event admission

Every writer uses the shared append transaction described in
[events.md, "Admission"](events.md#admission). `page init` also checks the
standing log against the replacement layer's stored-record contracts before
re-vendoring.

## Static validation

`page check` starts with a deterministic check of the exact mutable `index.html`
(no browser, near-free; activation and `page stamp` run the same boundary): the HTML parses with balanced
tags; one direct `<body><main>` contains all authored content; page-authored behavior
runs after the runtime has read the page, as inline modules, deferred classic script
files, or their literal local graphs rooted below `/page/`, never parser-blocking or
`async` scripts; page-specific presentation appears inline or in captured `/page/`
stylesheets; anything on another server is named by its http(s) URL and loaded as
written. The encoding, runtime, theme, page identity, canonical address, and anything
declared about the whole document (a `<base>`, an http-equiv `<meta>`, an import map)
belong to delivery and are rejected in source, and the last three in message markup
too, which renders in every revision. Delivery inserts them at the start of
`<head>`, before authored executable content. Every lf-* element validates against the effective registry
(schema, nesting, no self-closing form); every lf-* meta is a known page
declaration with an allowed value; each lf-suggestion is well formed (at most
one of each slot, at least one of them, no nesting, `resolves` naming a comment
in the document's reference namespace); ids are unique and hold no whitespace, no authored id, class, or
attribute sits in the runtime's `lf-` and `data-lf-` namespaces, named today or
not, no id takes the shape of the event ids the log mints (`schema.EVENT_ID`), since
a command's ID names a widget or a message in one address space, and ids needed by anchored unresolved threads, standing user actions, or
effective standing reports survive from the previous revision. A
declared visual part survives on the same terms as an id: while a live
thread's current anchor names it, and no longer once every thread on it
has moved, detached, or closed. That release is final — a revision the part has
left cannot be asked for it back, so reopening the closed thread restores
the thread and not its target. An agent reply may detach a thread in the same
transition that removes its subject. A declared retirement protects its holder and slots until its
outcome licenses their removal. Other dropped ids are reported as advice. These carry-over rules judge a candidate. A source whose captured artifact is the active revision's had its transition judged when it activated, and the append door has judged every event since against the revision it names, so neither activation nor `page check` re-judges it against the longer log. Near-free
and deterministic is what makes running it on every save affordable, so keep a new
check that way; anything needing a browser belongs in the command's browser half.
The effective registry is validated where it differs from the active revision's
captured copy, which was validated when that revision activated; vendored sheets are
validated when `page init` composes them, not on each check.

That half has one piece plain `page check` runs too. A page that runs code of its
own, a module script or a page widget the document places, or places a data widget
(`x-content: data`), is served and run once at the render viewport through upgrade,
presentation, and one frame after it, and fails on each `error` event its runtime posts
in that time: the event `leaf wait` would deliver, intercepted rather than read off the
browser's own error channels, so the check and the watcher fail on one set in one
wording. A widget that fails soft posts one too. A quick page never reaches `--render`,
and no static reading says whether a module throws or whether a data body is one its
module can read. Message markup that places a data or page widget is run the same way,
as a page of its own, before the thread command that carries it takes the log: the log
freezes it, and a chart in a shut thread has no room to draw in any later run. A run
serves the page's log, so what earlier messages place runs in it too; the post-time run
is what keeps those clean. Leaf runs without a browser, so where the host has none,
every browser gate (these runs, `--render`, and `package check --render`) is skipped
with a note and leaves the status alone: the page posts the same `error` events
whenever a browser draws it, so a browserless host such as leaf.page's container loses
the early reading, not the report.
`render_gate/page_code.py` owns the run.

An ordinary document's thread namespace is the thread ids its log holds,
including a thread whose opening comment the log lost. A sample template's
namespace comes from its initial history. `sample_content.initial_sample_events`
constructs it once for both static validation and allocation. `data-sample-events`
names an inline inert JSON script in the captured parent document: its ordinary event
commands are admitted against the child, including file-side anchor capture and the
shared message-markup gate. The resulting history defines the child's thread namespace
before presentation and never writes the parent's log.

Alternatively, `data-sample-threads` selects from the parent's available history.
A first version may name threads whose seed log has not been written yet; a thread
the log does not hold leaves the child without it rather than refusing the page.
Corpus generation selects against the shipped log it is composing from, where a
declared thread the log lacks is a mistake in the declaration, and refuses it.
The two history declarations are mutually exclusive.

## Delivery policy

A page carries no content policy of its own: its code is its author's, and may load,
fetch, and compile what it likes. Every served HTML response adds one header,
`frame-ancestors 'self'` (`structure.FRAME_ANCESTORS_CSP`). Same-origin parents may
embed a live page: they already share its DOM and request authority. A different
origin cannot disguise its decisions under another interface, even when same-site
cookies authorize the framed request. Historical versions and sample children
receive the same header. The published site's Worker reads it from the site
manifest for HTML served from its own assets. A standalone file has no response
header and cannot make this framing guarantee. Every response carries
`X-Content-Type-Options: nosniff`; typed data is available only through its JSON
API, and media routes serve only admitted image types, so neither input surface
can become a script module.

## Browser validation

`page check --render` adds the rest of the browser half, run once before a page's URL is first
handed over: the exact current source loads in the host's browser (whichever
executable `LEAF_BROWSER_EXECUTABLE`, `CHROME_PATH`, or `CHROME_BIN` names, else
Playwright's `channel="chrome"`, else the first browser `PATH` answers with) and the
render invariants the static lint cannot reach run against it in both color schemes:
no console or page errors, no issue Chrome's DevTools raises (an unsized lazy
image, a blocked or mixed-content request, a deprecated API) outside a form control's
shadow tree, one in an embedded frame placed at that frame (a widget failing soft
is a console error, since the page reports it);
every widget upgraded, painted with values that resolve, and given real space;
words a user can mark, reach, and select, with the registry's verbatim and shadow
declarations honored; no sideways scroll, clipped control, squeezed table, or
misplaced box; and standing state that replays without conflict and idempotently.
`render_gate/readings.py` is the list. Those readings run
at a desktop and a phone viewport; once they are done, the loaded desktop page is
resized through the widths from 360px to 1920px and the two sideways readings are taken
again at each: a version holds at every width from the narrowest phone to a wide
desktop, not only at the two the gate renders, and each fault the sweep alone finds is
reported with the widths it spans. The sweep also finds each width where the page's own
margin residents change (`data-lf-margin` on `main`, less the rail), and the readings
run again there in the light scheme, where each resident has the least room it will
ever have. It reads, too, how each flex or grid box the page wrote splits its children
into rows, and the swept widths where that changes, and it fails a workspace whose panes
stand side by side at the desktop viewport and stack in one column at a width where the
Layout still fills the window, since stacked there they share one window's height. A
body of rows at the desktop viewport is a design of rows, whatever a wider window does.

A version that passes gets screens for the author to read (`render_gate/screens.py`):
the page's first eight screens down from its top at the desktop viewport, at the
sweep's widest width and on a 390px phone, each pass's label saying how many screens the
whole page takes when it takes more, and one screen at each swept width where the page's
arrangement is at its tightest before it changes, and at each margin width. They go to one directory per page under the state home's
`screens/`, replaced whole at each check, which the command names. The arrangement is
read with the sweep, a few milliseconds a width; the screens are the command's, not the
gate's, and the suite, which reads render_version, takes none.
The invariants live in render_version, which the tests/test_render_*.py modules drive over
the shipped examples. The suite uses Chromium's headless shell, while its
end-to-end render-check tests run the launches used here — the installed Chrome
channel, and the headless shell handed over under each variable that names one —
and a unit reading covers the PATH search, which is only reached where the channel
misses.
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

The render gate serves its probe modules from the Leaf running the command and the
runtime those modules import from the page, so the ephemeral server it opens refuses
a page whose recorded `$layer.runtime` is not the identity this payload's kernel
runtime carries — the refusal every page server makes (`layer-registry.md`, `runtime`).
Without it the mismatch arrives as a missing export in the probe module, which reads
as a defect in the page. The vendored layer is the page's to keep, so the gate does
not re-vendor on its behalf.

## Passages

An anchor is resolved in the browser and recorded in the event log, so
`leaf thread open` reads the active revision the way the anchor pass reads the DOM — text in
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
authored version and uses the thread's whole action window.
Runtime anchors are already resolved against rendered words, including widget
labels and module output unavailable to the file reading, so admission does not
recapture them. Browser `quoteFrom` and Python's `COLLAPSE_CHARS` define matching
whitespace collapse. `leaf thread open` captures its quote against the file reading
before it writes: a quote must be unique in its declared section, and widget source,
retired text, and repeated passages are refused.

## Parsed source

A page source is written in more than one language. TurboHTML's WHATWG tree drives
the one SourceDocument reading of what the markup declares and says;
SourceDocument also retains exact source spans. tinycss2 reads the CSS a <style> block
holds; layout advice also reads the stylesheets the page links from `page/`, as the
revision's capture resolves them (`RevisionArtifact.page_stylesheets`). A new question about a page becomes a field on one of those readings rather
than a pattern over the file's text, because a pattern answers something adjacent to
the question asked.

Immutable inputs are read once per process. A stored revision's document, captured
vocabulary, and passage readings live on its one `RevisionReading`
(`revision_artifact.read_revision`); a candidate's live on the one `SourceReading`
its check takes, which the revision activation writes from it adopts. Each logged
markup fragment is parsed once (`thread_context.logged_fragment`), while markup a
writer hands in is parsed afresh at its gate.
