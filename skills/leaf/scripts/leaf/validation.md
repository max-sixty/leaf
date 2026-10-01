# Validation contract

Each input is validated once, where it enters, and code past that point reads it
directly:

- an event, whether a browser posted it or a command wrote it, at the append door
  ([events.md, "Admission"](events.md#admission));
- a page's authored source at `check_source` (`validation/source.py`), which `page
  check`, activation, `page stamp`, and `page init` all run ("Static validation");
- message markup an agent hands in at `admission.check_markup`, which applies the same
  vocabulary checks to a fragment;
- a layer `page init` would vendor at `compatibility.incoming_registry`, and against the
  standing log at `compatibility.candidate_vocabulary_gaps`, which refuses a layer that
  drops an event kind, reaction token, verb, visual part, or thread-markup contract the
  log still uses;
- what only a browser can see at `page check --render` ("Browser validation").

## Static validation

The static check is a deterministic reading of the exact `index.html` with no browser,
cheap enough to run on every save. A new check that needs a browser goes in the browser
half. It refuses:

- **Shape.** Unparsable or unbalanced HTML, and any authored content outside the one
  `<main>` directly under `<body>`.
- **Executable content.** A page's own script that runs before the runtime has read the
  page: a parser-blocking or `async` script. Page code is an inline module, a deferred
  classic script file, or the literal local import graph of one under `/page/`; page
  styles are inline or captured `/page/` stylesheets. A resource on another server is
  named by its http(s) URL and loaded as written.
- **Delivery's declarations.** The encoding, runtime, theme, page identity, canonical
  address, `<base>`, http-equiv `<meta>`, and import map belong to delivery, which
  inserts its own at the start of `<head>`. Message markup is refused the last three
  too, since it renders in every revision.
- **Vocabulary.** An `lf-*` element that fails the effective registry (schema, nesting,
  self-closing form), an unknown `lf-*` meta or value, and an `lf-suggestion` with no
  slot, two of one slot, a nested suggestion, or a `resolves` naming no thread in the
  document's thread namespace.
- **Ids.** A duplicate id or one holding whitespace; any authored id, class, or
  attribute under the runtime's `lf-` or `data-lf-` prefix; and an id shaped like a
  logged event id (`schema.EVENT_ID`), since a command's id names a widget or a message
  in one address space.

The registry is validated only where it differs from the active revision's captured
copy, and vendored sheets when `page init` composes them.

### Carry-over

A candidate keeps every id that an anchored unresolved thread, a standing user action,
or an effective standing report needs from the previous revision, and every element a
declared retirement holds until its outcome licenses removal. A declared visual part
is kept while a live thread's current anchor names it; once every thread on it has
moved, detached, or closed, a revision may drop it, and reopening the thread does not
bring it back. An agent reply may detach a thread in the same transition that removes
its subject. Other dropped ids are advice. Each refusal names its way out
(`source_history.PROTECTED_REMEDIES`).

Only a candidate is judged. A source whose artifact is the active revision's was judged
when it activated, and the door has judged every event since, so `page check` does not
re-judge it against the longer log (`revisioning.py`).

### Thread namespaces

A thread reference such as `resolves` is checked against the thread ids the log holds
(`thread_context.thread_ids`), including a thread whose opening comment the log lost. A
sample template's namespace is its `data-sample-threads`, so a first version may name
threads its seed log does not hold yet: the child is checked with whatever history is
available, and allocation copies that same history, leaving out a thread the log lacks.
Corpus generation composes from the shipped log, so there a declared thread the log
lacks is a typo and is refused.

### Page code

Plain `page check` runs a page that carries code of its own once in a browser, and fails
on each `error` event the runtime posts, the same set `leaf wait` delivers
(`render_gate/page_code.py`).

## Delivery policy

A page carries no content policy: its code is its author's. Every served HTML response,
historical version routes included, adds `frame-ancestors 'none'`
(`structure.FRAME_ANCESTORS_CSP`), so no other site can frame a live page and take a
click meant for one of its decisions; the site's Worker reads the same value from the
site manifest. A sample child allows its same-origin parent (`frame-ancestors 'self'`).
A standalone file has no response header and so no framing guarantee. Every response
carries `X-Content-Type-Options: nosniff`, and data and media routes serve only their
JSON and admitted image types, so neither can be imported as a script.

## Browser validation

`page check --render` loads the exact source once before a page's URL is first handed
over, in the host's browser (`render_gate/browser.py` resolves it), and refuses a page
only for a fault its author can fix by editing it; a fault in Leaf's own chrome or
theme belongs in the suite. `render_version` is the one implementation, called by the
command and by the `tests/test_render_*.py` modules over the shipped examples.
`render_gate/version.py` sequences it, `scheme.py` and `readings.py` take the readings,
and `render-checks/` holds the probes the table names.

The readings run at 1200×900 and 540×720 in both color schemes, except the
scheme-blind ones, `missingThreads` through `relativeReplays`, which run in the light
scheme only. Once per version, on the light desktop page, the advice readings run and
the page is resized through 360–1920px in 40px steps to read `rootOverflow` and
`misplacedBoxes` again, and `arrangedBoxes` and `heldPanes`, which run only there. A
fault only this sweep finds is reported with the widths it spans. Each width where the
page's own margin content changes (`data-lf-margin` on `main`, less the rail) is then
rendered in the light scheme too.

| Reading | Contract |
| --- | --- |
| pre-upgrade proof (`start_with_pre_upgrade_proof`, `preUpgradeFindings`) | while the Leaf entry is held: one canonical Leaf entry, one direct `main` with layout, and no widget upgraded or readiness stamp before the entry runs |
| `runtimeStarted` | the runtime injected its chrome |
| console, `pageerror`, failed responses | no console error or warning, uncaught error, or failed response; a ResizeObserver loop notice fails only if a second complete attempt reports it again |
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
| `shownVerbatim` | each `x-verbatim` owner shows the words of its projected passage, the one a user can point at |
| `missingThreads` | every `x-thread-seat` instance outside thread chrome holds exactly one thread seat |
| `silentWords` | `x-says` and `x-paints` promises reach the rendered page |
| `undeclaredAttrs` | modules write no undeclared author-namespace state |
| `retiredSlots` | settlement marks agree with the projection |
| `replayOverrides` | no attribute or placement fact is changed both by the author and by a user action carried from an earlier revision; the log's value would silently override the markup |
| `relativeReplays` | rendering a complete widget state twice changes nothing |
| `shrunkLabels` | advice only: a drawing scaled so far that its labels fall below a legible size |
| `unreservedHeights` | advice only: an `x-height` widget drew at a height its first paint did not reserve |
| `arrangedBoxes` | advice only: the swept widths where a flex or grid box the page wrote splits its children into rows differently |
| `heldPanes` | a workspace whose panes sit side by side at the desktop viewport does not stack them in one column at a width where the Layout still fills the window, since stacked there they share one window's height |
| `trappedMargins`, `splitEdges`, `apparatusAmongAuthored` | suite only: the theme's frame trim reaches Leaf's own boxes, and the runtime adds nothing among the page's own elements |

A version that passes gets screens for its author to read, saved under the state
home's `screens/` and named by the command (`render_gate/screens.py`); `render_version`
alone saves none.

## Passages

The browser resolves an anchor and records it in the log; `leaf thread open` reads the
active revision's file instead (`passages.py`). The two must read the same words, so
the file reading mirrors the runtime's capture: the same skipped runtime words, block
boundaries, and whitespace collapse (`passages.COLLAPSE_CHARS`, the browser's
`collapse.js`). Where the file cannot know what a module will write, the registry says
(`x-says`, `x-verbatim`, `x-retired-when`), and any other upgraded element is fenced.
A quote never spans a fence, so a passage the file cannot read is refused when the
comment is written rather than detaching later in the user's browser; anchor on the
widget's element (`--section`) instead. A file-side quote must also be unique in its
declared section, and widget source and retired text are refused. Runtime anchors were
resolved against rendered words, so admission does not recapture them.

## Parsed source

TurboHTML's tree drives the one `SourceDocument` reading of what markup declares and
says, with exact source spans; tinycss2 reads `<style>` blocks and the `/page/`
stylesheets a revision captured (`RevisionArtifact.page_stylesheets`). A new question
about a page becomes a field on one of those readings, not a pattern over the file's
text.

Immutable inputs are read once per process: a stored revision through
`revision_artifact.read_revision`, a candidate through the one `SourceReading` its
check takes (which the revision it activates adopts), and logged markup through
`thread_context.logged_fragment`. Markup a writer hands in is parsed afresh at its
gate.
