# Page instance boundary

The page instance is Leaf's complete authored artifact. Packages contribute reusable
code and vocabulary; the composed layer supplies Leaf's shared runtime; a reader session
temporarily operates one page instance. Packaging changes who maintains and reuses code.
It does not isolate code that executes in the same page.

This note specifies the changes needed to make that ownership model true. The canonical
terms live in the [glossary](../.claude/skills/developing-leaf/references/glossary.md).
The implementation contracts replace this note as each part ships.

This plan and the [reactive browser runtime](reactive-browser-runtime.md) are one
program. This note owns revision contents, page and package composition, stable identity,
and export modes. The runtime plan owns semantic publication, rendering, and presentation
inside each active document. Neither plan introduces a second state path or a second
export runtime. The [Playground capability plan](playground-capability-plan.md) consumes
the combined result.

The current seams are the [page storage](../skills/leaf/scripts/leaf/page-storage.md),
[layer and registry](../skills/leaf/scripts/leaf/layer-registry.md),
[validation](../skills/leaf/scripts/leaf/validation.md), and
[event](../skills/leaf/scripts/leaf/events.md) contracts. Consumer-facing rules live in
[page authoring](../skills/leaf/references/page-authoring.md) and
[package authoring](../skills/leaf/references/packages.md). Implementations change those
contracts and their code together.

## Ownership

| Owner | Owns |
|---|---|
| Core Leaf | Revision activation, scoped serving, executable and inert-input boundaries, stable target and reference identity, event admission and projection, requests, comments, runtime chrome, and export modes |
| Package | Reusable declarations, widgets, controllers, browser modules, styles, data contracts, and guidance |
| Page instance | Authored content, page-local module/style/asset graph, page-specific declarations, semantic target choices, drafts, and selected packages |
| Reader session | Focus, scroll, selection, and disposable exploration state |

Durable reader choices enter the page instance through Leaf's typed event path. A page
module does not gain a second event store, and a page-owned declaration does not gain a
second admission path.

## Required contracts

### #1 — A revision captures one complete page

The author may place page-specific modules, styles, and supporting files below
`<page>/page/` and reference them from `index.html` with canonical `/page/…` paths. Leaf
activates the HTML and its complete local dependency graph as one revision. A package is
still the source for behavior or vocabulary reused across pages.

The author-facing paths stay stable. Each served live, historical, MCP, published, and
exported document resolves them to bytes captured for that revision. The captured graph
also binds the effective registry and the immutable selected layer and runtime
dependencies that document uses; a historical revision never imports replacement layer
bytes. The server never serves mutable author source directly.

Relative module imports, CSS imports, and CSS URL dependencies stay within the captured
page graph. Page modules may import only the public layer entry points recorded in the
revision manifest, including `runtime/widget-api.js`. An unresolved dependency, network
dependency, arbitrary filesystem escape, or import of an undeclared layer-internal path
refuses activation. The revision store may deduplicate bytes by digest, but deduplication
is not part of the author contract.

Every live revision activates in a fresh document execution environment. Markup-only DOM
replacement and executable reload are not separate paths, and candidate page modules
never run in the old environment. Automatic activation waits while composition or
dragging is active. Before navigation, Leaf records only its explicit continuity state;
the new document revalidates recoverable drafts, reading position, and standing
destinations, and reconciles the reactive runtime's bounded unresolved ledger. Element
instances, arbitrary module state, and exact focus inside an interrupted interaction do
not cross the boundary. Leaf may optimize activation later only if a measurement
justifies it and the optimized path preserves this lifecycle.

Inline modules remain valid and keep their exact CSP hashes. Captured external modules
are explicit same-origin module sources served with strict MIME types. Classic scripts,
event-handler attributes, and `javascript:` URLs remain invalid. Typed data and media
remain inert: neither can be imported as code or interpreted as markup.

Done means:

- an edit to a local module and its markup becomes observable together without a manual
  reload;
- a stamped historical version continues to execute its captured module graph after the
  mutable source changes;
- relative imports and CSS dependencies work at live, historical, MCP, published, and
  interactive-export addresses;
- traversal, unresolved dependencies, executable data, wrong MIME types, and network
  dependencies fail before activation; and
- `page state`, version checks, and diagnostics identify the complete candidate and the
  file that refused it.

### #2 — A page may declare its own typed state

A page instance may contribute element, action, report, request, and data declarations
from `<page>/page/registry.json`, using the same declaration language as packages. Leaf
composes the page contribution after the selected layer and binds the effective registry
to the revision that uses it. A later declaration replaces one complete entry rather
than deep-merging its schema. Declaration ownership and implementation source resolve
independently: replacing a package element's declaration without supplying a page widget
retains the selected package's implementation, while a page-supplied implementation is
captured from `<page>/page/widgets/<tag>.js`. The revision manifest fixes that choice.
This permits a page to give `lf-playground` an exact task-specific action schema without
copying or wrapping its package module. The contribution is not an implicit package: it
has no install name, no package selection, and no reach beyond that page instance.

The existing registry validator, browser schema, append transaction, state fold, undo,
request lifecycle, projection, and version checks consume the effective revision-bound
registry. Previously accepted events remain interpretable after a later revision changes
or removes a page-owned declaration. Page modules submit through the public widget API;
they cannot append arbitrary events or supply server-owned meaning.

Disposable simulation state stays in the reader session. Recoverable unsent drafts stay
scoped to the page instance in browser storage. Submitted choices use declared state and
the shared event log. Page-local editable configuration remains draft or session state
until submission; the one reactive application snapshot does not turn every local
control edit into a durable semantic event.

Done means a one-page explorer can submit nested JSON-safe configuration, restore it,
undo it, carry it across a revision, and expose it through `page state` without creating
a package or a parallel state store.

### #7 — Core owns identity; authors choose semantics

Core Leaf owns stable references, revision context, target resolution, detached and
ambiguous states, hit testing, keyboard targeting, and validation of declared references.
A package may provide reusable selection or editing controllers. The page instance
chooses which semantic boundaries, relationships, properties, and controls fit its
artifact.

A change may name several targets with explicit roles such as `source`, `reference`, or
`container`. Identity comes from authored ids or Leaf's structural target record, never
from labels or prose. Core does not impose a fixed ancestor count, CSS-property list,
value grammar, or one-target instruction shape.

Done means a page can express a relational change such as aligning one selected element
to another while both identities survive revision, replay, and comment navigation.

### Design comments carry intent, not ownership

Design mode records that the reader is commenting on presentation or interaction. It
does not assert that the composed layer owns the requested change. The agent inspects the
current source owner and changes the page instance unless the affected behavior is
already reusable or the reader asks for broader reach.

Design-mode comments carry `about: "design"` instead of assigning `about: "layer"`.
The reader is not asked to classify the source owner before describing the change.
Existing anchors and conversation semantics remain the route back to the requested
surface.

Done means the same design gesture can lead to an inline page style, a page module, a
selected package, or core Leaf without changing the reader's interaction or losing the
original intent.

### #5 — Export states its execution mode

Static export remains a script-free snapshot. Interactive export captures the active
revision's page-owned and layer-owned local dependencies, preserves local computation
and navigation, and disables every host-dependent action. A disabled action says that no
agent or server is available; it never appears accepted.

Interactive export follows dependency capture in #1. It is not a reason to retain live
networking, bootstrap probes, event submission, or host chrome in a standalone file.
The reactive runtime's normal renderers and presentation barrier serve both live and
offline-interactive documents; export does not add a parallel page runtime.

Done means the same playground can be exported either as a readable static record or as
an offline interactive artifact whose local controls work and whose host actions cannot
run.

## Implementation order

1. Complete #1's dependency capture and fresh-document activation path.
2. Use the reactive runtime's joint validation slice to establish its final public
   behavior API and compose one revision-bound page declaration through the existing
   registry and event machinery (#2).
3. Complete the reactive publisher, rendering, and presentation cutover against that
   page-owned case.
4. Separate design intent from source ownership and expose identity controllers needed
   by #7.
5. Build interactive export on the captured revision graph and shared presentation
   barrier (#5).

Each slice replaces the corresponding future-tense rules here with implementation
contracts beside the owning code. The final slice deletes this note and its link from the
joint `TODO.md` item. That item remains until both the page-instance and reactive-runtime
outcomes are complete.

## Acceptance set

Exercise the complete boundary with:

- a one-off simulator whose page module imports a local helper;
- a structured explorer with dynamic rows and nested submitted state;
- a relational editor that names two targets;
- a reused package widget beside page-owned behavior;
- a stamped revision opened after every mutable source file has changed;
- reconnect, replay, undo, and a design comment on page-owned presentation; and
- static and offline-interactive exports of the same page.

These cases use the real server, browser, event log, and exported artifacts. Unit tests
may cover parsers and storage details, but they do not replace the end-to-end boundary.
