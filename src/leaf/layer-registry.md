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

Reading a page's documents, state or instructions needs only its layer's
vocabulary: the merged registry, the paths of the widget modules and the packages'
instructions. Leaf validates the merged registry, and parses the layer's sheets and
modules, only to serve, export, check or inspect the page, or to capture a revision
whose markup names a file the layer serves. A package that stops composing after
`page init`, as a copy edited in place or a registry or sheet a stricter Leaf
refuses, is refused there: `page check` and `server start` refuse it, naming the
repair, while hooks and reads of the page go on.

The layer record holds the selection and two identities:

- `packages` records content-package selections. `theme` is the separately selected
  theme, the page's look, `{name, source}` with `source` explicit or default. A new
  page takes the user's default or else Leaf's bundled `reading`; null records taking
  none.
  The reading look and then the theme compose right after the default package,
  before the content packages (`themes.with_theme`), so a theme restates the look
  and a content package restates either. Re-running `page init` preserves
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
incarnation (`Leaf-Server`), the layer generation or the website release changes, and
once, marked, when a page that could not start for lack of something it needs finds
its own server answering. A rejected or unchanged `page init` keeps the server and
the generation, so open tabs don't reload.

## Page protocol

The layer record's `protocol` is the page protocol: the version of what a page keeps
across Leaf versions, the kernel event records in its log and the records Leaf keeps
outside the page. Root `AGENTS.md`, "Pages across Leaf updates", says when it moves.

Every page server and the append door refuse a page at another number
(`layer.incompatible_layer` says what each refusal names). The session holding a page
at a lower number takes it to this Leaf's at its first write command or hook naming the
page (`vendoring.renew_layer`); read commands leave it and its server alone. No Leaf
takes a page down. `session_runtime.py` selects the Leaf that runs a session's hooks
and watch.

A Leaf's readings skip an event kind it doesn't know, and its deliveries hand such an
event over as logged, with no handling clause. So a new kind declares `skippable` where
that leaves an older Leaf's reading right, and bumps otherwise.

`build/browser/protocol-baseline.json` keeps `$events`, each `state.Record` schema and
the composer's draft as they stood at the current number, and
`build/browser/protocol.mjs` compares each build against it (its header says in which
direction for each schema). It refuses a change to an event record, or a new kind not
declared `skippable`, until the change takes what it took or the number moves.

The number also versions each record Leaf keeps outside a page's log and document:
every `state.Record` in a page directory or the state home, the layer record among
them, and the composer's draft (`$events.draft`). Each carries `leaf-<kind>/<since>` in
its `format`, where `since` is the protocol at which that record's shape last changed,
so a bump for another change leaves it readable. A new kind starts at the current
protocol without a bump, since no earlier Leaf reads it. A shape change that a reader at
the same format would misread sets `since` to the current protocol, bumping the
protocol first where `since` already names it. The build refuses a change at the same
`since` that a reader at either end would misread, and a `since` moved anywhere but the
current protocol. A reader treats a record at another format as absent, except a layer
record at a later shape than its own, which refuses the page as a newer Leaf's
(`registry.storage.layer_record`): read as absent, it would have `page init` replace
the page's selection.

## Composition stamps

Every composition, `page init`'s layer and a page's own declarations over it, writes
`$modules`, the module each declared element has among the files it composes
(`registry/contract.MODULES`): `widgets/<tag>.js` in the kernel or a package, or
`page/widgets/<tag>.js`, which wins. A tag with a module is an upgraded widget, and no
declaration says so. It then stamps the facts the browser reads rather than derives
(`registry/layer.stamp_composition`), overwriting any a layer declared: `$decisions`,
each widget's deciding `server.state` verb and the member tags each of its outcomes
retires, and `$states`, each verb's writer and the operation definition an admitted
event records. It also completes the attribute schemas validation reads: an attribute
naming one of the layer's words, such as a tone, takes the layer's list as its `enum`,
and an attribute holding a name Leaf looks up, such as an element id, takes that name's
grammar as its `pattern`.

The kernel registry, `browser/runtime/kernel-registry.json`, declares the other facts
both runtimes read (`registry.layer.KERNEL_FACTS`, described in `registry/kernel.py`'s
header, and the classifications on each `$events.kinds` entry). It is part of the
runtime, so both read the serving Leaf's copy, the browser through
`runtime/kernel-facts.js`. Composition lays each layer over it, none is stamped for
the browser to read, and a layer that changes one is refused.
