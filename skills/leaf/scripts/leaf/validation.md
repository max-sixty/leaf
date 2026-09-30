# Validation contract

## Event admission

Every writer uses the shared append transaction described in
[events.md, "Admission"](events.md#admission). `page init` also checks the
standing log against the replacement layer's stored-record contracts before
re-vendoring.

## Static validation

`page check` starts with a deterministic reading of the exact mutable `index.html`. It
needs no browser and costs almost nothing. Activation and `page stamp` run the same
check, cheap enough for every save. Keep a new check that way, and put anything that
needs a browser in the command's browser half.

- **Shape.** The HTML parses with balanced tags, and one direct `<body><main>` holds
  all authored content.
- **Executable content.** Page-authored behavior runs after the runtime has read the
  page, as inline modules, deferred classic script files, or their literal local
  graphs rooted below `/page/`, never as parser-blocking or `async` scripts.
  Page-specific presentation is inline or in captured `/page/` stylesheets. Anything
  on another server is named by its http(s) URL and loaded as written.
- **Owned by delivery.** The encoding, runtime, theme, page identity, canonical
  address, and anything declared about the whole document (a `<base>`, an
  http-equiv `<meta>`, an import map) belong to delivery and are refused in source.
  The last three are refused in message markup too, which renders in every revision.
  Delivery inserts what it owns at the start of `<head>`, before authored executable
  content.
- **Vocabulary.** Every `lf-*` element validates against the effective registry
  (schema, nesting, no self-closing form). Every `lf-*` meta is a known page
  declaration with an allowed value. Each `lf-suggestion` has at least one slot, at
  most one of each, no nesting, and a `resolves` naming a comment in the document's
  reference namespace.
- **Ids.** Ids are unique and hold no whitespace. No authored id, class, or attribute
  uses the runtime's `lf-` or `data-lf-` prefix, whether or not the runtime uses that
  name yet. No id has the shape of the event ids the log mints (`schema.EVENT_ID`),
  because a command's id names a widget or a message in one address space.

The effective registry is validated where it differs from the active revision's
captured copy, which was validated when that revision activated. Vendored sheets are
validated when `page init` composes them, not on each check.

### Carry-over

A candidate keeps every id that an anchored unresolved thread, a standing user action,
or an effective standing report needs from the previous revision. A declared visual
part is kept on the same terms: while a live thread's current anchor names it, and no
longer once every thread on it has moved, detached, or closed. That release is final.
A revision the part has left cannot be asked for it back, so reopening the closed
thread restores the thread and not its target. An agent reply may detach a thread in
the same transition that removes its subject. A declared retirement protects its
holder and slots until its outcome licenses their removal. Other dropped ids are
reported as advice.

These rules judge a candidate only. A source whose captured artifact is the active
revision's had its transition judged when it activated, and the append door has
judged every event since against the revision it names, so neither activation nor
`page check` re-judges that source against the longer log.

### Thread namespaces

An ordinary document's thread namespace is the thread ids its log holds,
including a thread whose opening comment the log lost. A sample template's
namespace is its `data-sample-threads` declaration, so a first version may name
threads whose seed log has not been written yet. Static validation applies the same
child-document checks using the selected history currently available. Sample
allocation copies that same available history and no more, so a thread the log does
not hold leaves the child without it rather than refusing the page. Corpus
generation selects against the shipped log it is composing from, where a declared
thread the log lacks is a mistake in the declaration, and refuses it.

### Page code

Plain `page check` also runs one browser check. A page that runs code of its own, a
module script or a page widget the document places, is served and run once at the
render viewport through upgrade, presentation, and one frame after it. It fails on
each `error` event its runtime posts in that time: the event `leaf wait` would
deliver, intercepted rather than read off the browser's own error channels, so the
check and the watcher fail on one set in one wording. A quick page never reaches
`--render`, and no static reading says whether a module throws.
`render_gate/page_code.py` owns the run.

## Delivery policy

A page carries no content policy of its own: its code is its author's, and may load,
fetch, and compile what it likes. Every ordinary served HTML response adds one header,
`frame-ancestors 'none'` (`structure.FRAME_ANCESTORS_CSP`), so no other site can frame
a live page and take a click meant for one of its decisions. Historical version routes
receive the same header. The published site's Worker adds the same header
to the HTML it serves from its own assets, reading it from the site manifest. A standalone
file has no response header and cannot make this framing guarantee. A sample child
permits its same-origin parent with `frame-ancestors 'self'`. Every response carries
`X-Content-Type-Options: nosniff`; typed data is available only through its JSON
API, and media routes serve only admitted image types, so neither input surface
can become a script module.

## Browser validation

`page check --render` adds the rest of the browser half, run once before a page's URL
is first handed over. The exact current source loads in the host's browser (whichever
executable `LEAF_BROWSER_EXECUTABLE`, `CHROME_PATH`, or `CHROME_BIN` names, else
Playwright's `channel="chrome"`, else the first browser `PATH` answers with), and the
readings below run against it at a 1200×900 and a 540×720 viewport, in both color
schemes. `render_gate/scheme.py` takes the load, readiness, and visual-part readings,
`render_gate/readings.py` the rest, and `render_gate/version.py` sequences the
viewports and the sweep; `render-checks/index.js` exports one probe per failure
class, which `render_checks.py` invokes.

| Reading | Contract |
| --- | --- |
| pre-upgrade proof (`start_with_pre_upgrade_proof`, `preUpgradeFindings`) | while the Leaf entry is held: one canonical Leaf entry, one direct `main` with layout, and no widget upgraded or readiness stamp before the entry runs |
| `runtimeStarted` | the runtime injected its chrome |
| console, `pageerror`, failed responses | no console error or warning, uncaught error, or failed response; a ResizeObserver loop notice fails only if a second complete attempt reports it again (`render_version`) |
| `issueNode` | no DevTools issue (an unsized lazy image, a blocked or mixed-content request, a deprecated API) outside a form control's shadow tree; one in an embedded frame is placed at that frame |
| `upgraded`, `wait_until_ready`, `pageSettled` (`moving`) | upgrade completed, the page reached readiness against the state read (`PageNotReady` otherwise), and geometry settled |
| `invalidVisualProviders`, `unrevealedVisualProviders` | each `x-visual` widget registers valid parts, and every authored part resolves, in the current state or after its `reveal` |
| `failSoftErrors` | no widget failed soft into an error box |
| `missingUpgrades` | every widget on the page whose entry declares a module defined its element |
| `invalidPaints` | every var()-backed SVG paint resolves |
| `tinyBoxes` | every declared widget has a usable box |
| `unmarkableElements` | every addressable element has a visible part to outline |
| `rootOverflow`, `misplacedBoxes` | no sideways scroll; boxes stay in the column or in reachable overflow |
| `strandedMargins` | every margin marker has an element to sit by |
| `squeezedTables` | a table scrolls sideways only with every column at its longest unbreakable run |
| `clippedControls` | controls are visible and reachable |
| `unreachableWords`, `coveredWords` | visible words stay in reachable flow and are not silently clipped or covered by chrome |
| `unreadSyntax` | highlighting does not alter source words |
| `undeclaredShadowRoots` | every shadow root outside generated controls is on a tag whose entry declares `x-shadow` |
| `shownVerbatim` | preserving owners agree with their projected passage |
| `missingThreads` | every `x-thread-seat` instance outside thread chrome holds exactly one thread seat |
| `silentWords` | `x-says` and `x-paints` promises reach the rendered page |
| `undeclaredAttrs` | modules write no undeclared author-namespace state |
| `retiredSlots` | settlement marks agree with the projection |
| `replayOverrides` | the log, not conflicting markup, determines projected state |
| `relativeReplays` | rendering a complete widget state twice changes nothing |
| `arrangedBoxes` | advice only. Records the swept widths where a flex or grid box the page wrote changes how it splits its children into rows; `screens.py` shoots each |
| `heldPanes` | a workspace whose panes sit side by side at the desktop viewport does not stack them in one column at a width where the Layout still fills the window, since stacked there they share one window's height |
| `shrunkLabels` | advice only: a drawing scaled so far that its labels fall below a legible size |
| `trappedMargins`, `splitEdges` | suite only: the theme's frame trim reaches Leaf's own boxes |

`missingThreads`, `silentWords`, `undeclaredAttrs`, `retiredSlots`, `replayOverrides`,
and `relativeReplays` read in the light scheme only, since the scheme changes none of
them. `shrunkLabels` reads the desktop viewport in the light scheme alone, and that
loaded page is then resized through the widths from 360px to 1920px: `rootOverflow`
and `misplacedBoxes` are read again at each, and `arrangedBoxes` and `heldPanes` are
read only there. A version holds at every width from the narrowest phone to a wide
desktop, not only at the two the gate renders, and each fault the sweep alone finds is
reported with the widths it spans. The sweep also finds each width where the page's
own margin residents change (`data-lf-margin` on `main`, less the rail), and the
readings run again there in the light scheme, where each resident has the least room
it will ever have.

A version that passes gets screens for the author to read (`render_gate/screens.py`):
the page's first eight screens down from its top at the desktop viewport, at the
sweep's widest width and on a 390px phone, each pass's label saying how many screens
the whole page takes when it takes more, and one screen at each swept width where the
page's arrangement is at its tightest before it changes, and at each margin width.
They go to one directory per page under the state home's `screens/`, replaced whole
at each check, which the command names. The arrangement is read with the sweep, a few
milliseconds a width. `page check` saves the screens; `render_version`, which the
suite calls, does not.

The invariants live in `render_version`, which the `tests/test_render_*.py` modules
drive over the shipped examples. The suite uses Chromium's headless shell, while its
end-to-end render-check tests run the launches used here — the installed Chrome
channel, and the headless shell handed over under each variable that names one — and
a unit reading covers the `PATH` search, which is only reached where the channel
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

An anchor is resolved in the browser and recorded in the event log, so `leaf thread
open` reads the active revision the way the anchor pass reads the DOM — text in
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
The expected words are bounded as widget state is (root `AGENTS.md`, "The document
starts state; the log changes it").
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
revision's capture resolves them (`RevisionArtifact.page_stylesheets`). A new question
about a page becomes a field on one of those readings rather than a pattern over the
file's text, because a pattern answers something adjacent to the question asked.

Immutable inputs are read once per process. A stored revision's document, captured
vocabulary, and passage readings live on its one `RevisionReading`
(`revision_artifact.read_revision`). A candidate's live on the one `SourceReading` its
check takes, and the revision activated from that candidate adopts it
(`RevisionReading(adopted=…)`). Each logged
markup fragment is parsed once (`thread_context.logged_fragment`), while markup a
writer hands in is parsed afresh at its gate.
