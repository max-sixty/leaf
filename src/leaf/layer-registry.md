# Layer composition and registry contract

A page records the packages and theme it selects in `layer.json`
(`registry.storage.LAYER`), never the layer itself. Every Leaf that serves, checks or
exports the page composes the layer from that selection, its own core and bundled
packages and the user's installed ones, in the order and at the merge grains of
`../../skills/leaf/references/packages.md`, "Package contract"; `registry/layer.py`
is the merge and `layer.selected_layer` holds the result for the process. The browser
runtime comes from the same Leaf (`runtime_selection.py`), so a page's widgets,
theme, vocabulary and runtime always ship together. Each revision captures its
authored content, its own declarations and modules, and names the selection, so an
approved version keeps what its user wrote and decided while the current Leaf draws
it. `page init` writes the selection; re-running it with another selection restarts a
served page's server (`../../skills/leaf/references/serving-pages.md`, "Leaf
updates"). `vendoring.cmd_init` decides whether it changes anything, and `page init
--dry-run` reports that decision as `changed` without writing or stopping the server.
The page lock serializes it with service changes and contract-bearing writes
(`page-storage.md`).

A selection must compose, and the page's own declarations must validate over the
layer, before `page init` writes it. Historical actions and reports never veto a
layer. Each admitted state gesture records its operation and detail domain in
`meaning.state`, so a decision the current domain still accepts keeps painting, and
one outside it, or whose sender is gone, stays in history only.

The layer record holds the selection and two identities:

- `packages` records content-package selections. `theme` is the separately selected
  theme, the page's look, `{name, source}` with `source` explicit or default. A new
  page takes the user's default or else Leaf's bundled `reading`; null, a record that
  names no choice, reads as `reading` too, and taking none is recorded explicitly as
  the reserved name `none` (`themes.theme_package`).
  The theme composes after the content packages. Re-running `page init` preserves
  the recorded choice until `--theme` replaces it or `--no-theme` clears it. User
  catalogue changes affect new pages; `themes.py` owns selection and
  `package-themes.md` documents its authoring interface.
- `generation`, a fresh epoch whenever the selection or the page protocol changes.
  The served registry names it under `$layer`, a served document names the
  generation of the revision it shows, event requests carry it, and contract
  responses repeat it, so a tab holding an old selection refuses a foreign answer
  rather than letting a replacement server interpret its event. The tab reloads only
  once its registry probe also reports the new generation, since a server running
  behind the document it served would hand back the same document. A revision's
  executable digest includes the generation, so a new selection gives an open tab a
  new document rather than a patch.
- `protocol`, the page protocol a Leaf last initialized the page at ("Page
  protocol").

The runtime and layer a document executes are named apart from these, by the identity
`runtime_selection.py` gives the serving Leaf's runtime, which covers every layer
input its tree holds. Where no website release names the runtime, a served document
names it (`data-lf-runtime-identity`), its resources are addressed under it, every
answer names the server's (`Leaf-Runtime`), and a tab names its own on every write.
Each side refuses the other's message naming another runtime, so a tab from before a
restart under an updated Leaf reloads rather than reading or writing with code the
server no longer runs. The served state names the layer's `fingerprint` and this Leaf
as its `producer` (`registry.storage.served_layer`), which the panel's menu (Copy Leaf
version) shows.

A served page's bootstrap (`runtime/bootstrap.js`) reloads the tab when the server
incarnation (`Leaf-Server`), the layer generation or the website release changes. A
rejected or unchanged `page init` keeps the server and the generation, so open tabs
don't reload.

## Page protocol

The layer record's `protocol` numbers the contract between a page and any Leaf that
serves it or writes its log. Since every Leaf composes a page's layer and supplies its
runtime itself, the contract covers only what a page keeps across Leaf versions: the
kernel event records in its log and their ownership, and the records Leaf keeps
outside a page. Every page server and the append door refuse a page at another number
(`layer.incompatible_layer` says what each refusal names). A page at a lower number is
taken to this Leaf's by the session holding it, at its first write command or hook
naming the page (`vendoring.renew_layer`); read commands leave it and its server
alone. No Leaf takes a page down.

Any Leaf at the page's number serves and writes it, so a plugin update leaves open
pages working. Admission validates a kernel record against the running Leaf's own
`$events` (`registry.kernel`), so a field a newer Leaf writes passes on a page an
older one initialized. The promise runs one way: an older Leaf may refuse a field it
does not know.

"Any Leaf at the page's number" is per process, and one session can run two. Claude
Code keeps a session on the plugin copy it loaded after its marketplace sweep installs
an update, until `/reload-plugins` or a restart, and a worktree's `bin/leaf` can take
a page the session holds past that copy's protocol. So the copy the session loaded
hands each hook, its watch and its bare `leaf` commands to the session's delivering
Leaf: the checkout that last initialized one of its pages, or a preview's, while it
exists, and otherwise the copy Claude Code installed since (`session_runtime.py`). An
update then reaches a session at its next hook; `hooks.json` and the hooks module,
which Claude Code reads as it loads the plugin, still wait for a reload. Where a
watch still can't read a page, as one started before this hand-off existed, its lease
names the older protocol it speaks, so a newer Leaf reads it as no watch and admission
nudges the session (`leases.wait_is_live`).

Bump the number when a Leaf at it would misread an event another Leaf at it wrote into
the log, or a record another wrote outside it. A change to the bundled widgets, their
registry entries, the theme or the public package API (`runtime/widget-api.js` and
its portable part `runtime/portable-api.js`) keeps the number, since the Leaf serving a page supplies all of them. A page's own widgets
and an installed package's modules call that API across Leaf versions, and a bump
would not repair them, since neither is re-composed from Leaf's tree; `page check
--render` and `package check --render` report a module an API change breaks.

The browser build holds the schemas to this. `build/browser/protocol-baseline.json`
keeps `$events`, each `state.Record` schema and the composer's draft as they stood at
the current number, and `build/browser/protocol.mjs` compares each build against it
(its header says in which direction for each schema). It refuses a change to an event
record until the change takes what it took or the number moves. A passing comparison
doesn't judge whether a bump chosen by hand was needed.
`served_state/state.schema.json` declares the served state and the `/api/view` answer
for the generated types and the producer's tests, outside the comparison.

The number is also the only version of what Leaf keeps outside a page's log and
document: every JSON record in a page directory or the state home (`state.Record`),
the layer record among them, and the composer's draft in browser storage
(`$events.draft`). Each carries `leaf-<kind>/<since>` in its `format`, where `since`
is the protocol at which that record's own shape last changed, so a bump for another
change leaves claims, deliveries and ports readable. A new record kind starts at the
current protocol without a bump, since earlier Leaves have no reader for it. A shape
change that a reader at the same format would misread sets `since` to the current
protocol, bumping the protocol first where `since` already names it. The build fails
a change at the same `since` that a reader at either end would misread, and a `since`
moved anywhere but the current protocol. A reader at another format treats a record
as absent.

## Composition stamps

Every composition, `page init`'s layer and a page's own declarations over it, stamps
the facts the browser reads rather than derives (`registry/layer.stamp_composition`),
overwriting any a layer declared: `$decisions`, each widget's deciding `x-state` verb
and the member tags each of its outcomes retires, and `$states`, each verb's writer
and the operation definition an admitted event records.

The kernel registry, `browser/runtime/kernel-registry.json`, declares the other facts
both runtimes read (`registry.layer.KERNEL_FACTS`, described in `registry/kernel.py`'s
header, and the classifications on each `$events.kinds` entry). It is part of the
runtime, so both read the serving Leaf's copy, the browser through
`runtime/kernel-facts.js`. Composition lays each layer over it, none is stamped for
the browser to read, and a layer that changes one is refused.
