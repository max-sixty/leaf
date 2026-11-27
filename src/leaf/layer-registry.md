# Layer composition and registry contract

A page records the packages it selects in `layer.json`
(`registry.storage.LAYER`), never the layer itself. Every Leaf that serves, checks or
exports the page composes the layer from that selection, its own core and bundled
packages and the user's installed ones, in the order and at the merge grains of
`../../skills/leaf/references/packages.md`, "Package contract"; `source/registry/layer.py`
is the merge and `layer.selected_layer` holds the result. The browser
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

The layer record holds the selection and an identity, and its `format` names the
page protocol ("Page protocol"):

- `packages` records the packages the page selects, in the order every Leaf composes
  them after the mandatory layer. A page's theme is one of them, Leaf's bundled
  `reading` included: Leaf composes no package the page doesn't list, so a page that
  lists no theme starts from the browser's defaults (`vendoring.py` states the
  decision). Re-running `page init` preserves the selection until `--package` or
  `--no-packages` replaces it. `package-themes.md`, "A page's theme", documents the
  authoring interface.
- `generation`, a fresh epoch whenever the selection or the page protocol changes.
  The served registry names it under `$layer`, a served document names the
  generation of the revision it shows, event requests carry it, and contract
  responses repeat it, so a tab holding an old selection refuses a foreign answer
  rather than letting a replacement server interpret its event. The tab reloads only
  once its registry probe also reports the new generation, since a server running
  behind the document it served would hand back the same document. A revision's
  executable digest includes the generation, so a new selection gives an open tab a
  new document rather than a patch.

The runtime and layer a document executes are named apart from these, by the identity
`runtime_selection.py` gives the serving Leaf's runtime, which covers every layer
input its tree holds. Where no website release names the runtime, a served document
names it (`data-lf-runtime-identity`), its resources are addressed under it, every
answer names the server's (`Leaf-Runtime`), and a tab names its own on every write.
Each side refuses the other's message naming another runtime, so a tab from before a
restart under an updated Leaf reloads rather than reading or writing with code the
server no longer runs. The served state names the layer's `fingerprint` and this Leaf
as its `producer` (`layer.served_layer`), which the panel's menu (Copy Leaf
version) shows.

A served page's bootstrap (`runtime/bootstrap.js`) reloads the tab when the server
incarnation (`Leaf-Server`), the layer generation or the website release changes, and
once, marked, when a page that could not start for lack of something it needs finds
its own server answering. A rejected or unchanged `page init` keeps the server and
the generation, so open tabs don't reload.

## Page protocol

The page protocol is the version of what a page keeps across Leaf versions: the kernel
event records in its log and the records Leaf keeps outside the page. Root `AGENTS.md`,
"Pages across Leaf updates", says when it moves. A page's protocol is the number in its
layer record's `format`, `leaf-layer/<protocol>`, which `page init` writes at the
protocol of the Leaf running it.

Every reader of the layer record decides by that number before it reads a field
(`registry.storage.layer_record`). At any number but this Leaf's, every page server
and the append door refuse the page, and so does every command that reads the page's
layer without renewing it, each naming the repair: a newer Leaf for a higher number,
since no Leaf takes a page down, and `page init` under this Leaf for a lower one. The
session holding a page at a lower number renews it at its first command that writes to
the page or hook that reads its pages (`vendoring.renew_layer` says which do); a
command that only reads the page leaves it and its server alone. A session's hooks and
watch run the copy of Leaf its harness loaded; `session-lifetime.md`, "Which Leaf runs
a session", says what another Leaf may do to the pages the session holds.

A change to the layer record's shape keeps `packages` as the page's selection, with the
same meaning. It is the one field a Leaf reads from another Leaf's record, so that
renewal keeps the page's selection (`registry.storage.layer_packages`).

A Leaf's readings skip an event kind it doesn't know, and its deliveries hand such an
event over as logged, with no handling clause. So a new kind declares `skippable` where
that leaves an older Leaf's reading right, and bumps otherwise.

`build/browser/protocol-baseline.json` keeps `$events`, each `state.Record` schema and
the composer's draft as they stood at the current number, and the build
(`build/browser/protocol.mjs`) refuses any change to an event record beyond its
annotations, or a new kind not declared `skippable`, until the number moves.

The number also versions each record Leaf keeps outside a page's log and document:
every `state.Record` in a page directory or the state home, and the composer's draft
(`$events.draft`). Each carries `leaf-<kind>/<since>` in its `format`, where `since` is
the protocol at which that record's shape last changed, so a bump for another change
leaves it readable. A new kind starts at the current protocol without a bump, since no
earlier Leaf reads it. A shape change sets `since` to the current protocol, bumping the
protocol first where `since` already names it, and the build refuses a shape change at
the same `since` or a `since` moved anywhere else.

Each shape of a record has a file of its own, named with its `since`
(`state.Record.file`), and a Leaf reads and replaces only the files of its own
shapes. So a Leaf finds a record of another shape as it finds none, and the Leaf that
wrote it finds it as it left it, however the two run beside each other. A record that
arbitrates between the Leaves on the machine, a page's claim with its session's
lifecycle, a page's service, a grant or the Codex adapter's, holds while a file of any
shape of it stands, whatever that file says: a Leaf refuses to act against it and
names the repair, and the acts that end one, a session's end, a stop, a withdrawal or
a takeover of the page, end it at every shape (`state.Record`). A session that ended
or died under a Leaf of another shape leaves that shape's lifecycle standing, so after
a `SESSION` shape change, which comes with a protocol bump, its pages stay held for
the newer Leaf until an agent's session takes each over with `leaf server start`,
which every refusal of a held page names. `page check` names a drafts store of
another shape, the user's unsent words, for the agent to point the user at; the
other records of other shapes are disposable. The layer record keeps one file, since its `format` is the page's
protocol (`registry.storage.write_layer`): its `since` is always the current protocol,
so a layer record at another format is another Leaf's page, read as above, and the
build lets its shape change only with a bump.

## Composition stamps

Every composition, `page init`'s layer and a page's own declarations over it, writes
`$modules`, the module each declared element has among the files it composes
(`source/registry/contract.MODULES`): `widgets/<tag>.js` in the kernel or a package, or
`page/widgets/<tag>.js`, which wins. A tag with a module is an upgraded widget, and no
declaration says so. Composition also writes into each declaration the defaults it
leaves out (`source/registry/contract.complete_declarations`): its `content`, its attribute
schema, the `type` and `additionalProperties` of that schema and of each verb's
`detail` schema, each verb's `unit` and its record's `kind`, and each attribute an
input binds by, as a string in the attribute
schema and, for the one its `reference` names, in `refers`. It writes them before
validation, so validation and every later reader read them whether the declaration or
composition wrote them.

Composition then stamps the facts the browser reads rather than derives
(`source/registry/layer.stamp_composition`), overwriting any a layer declared: `$decisions`,
each widget's deciding verb (`verbs`) and the member tags each of its outcomes
retires, and `$states`, each verb's writer and the operation definition an admitted
event records. It also completes the attribute schemas validation reads: an attribute
naming one of the layer's words, such as a tone, takes the layer's list as its `enum`,
every element takes an `id`, an attribute holding a name Leaf looks up, such as that
id, takes the name's grammar as its `pattern`, and a widget with a verb whose unit is
the whole widget takes the boolean attribute a version sets to take that verb back,
`restated` for the user's and `overruled` for the agent's.

The kernel registry, `browser/runtime/kernel-registry.json`, declares the other facts
both runtimes read (`registry.layer.KERNEL_FACTS`, described in `source/registry/kernel.py`'s
header, and the classifications on each `$events.kinds` entry). It is part of the
runtime, so both read the serving Leaf's copy, the browser through
`runtime/state/kernel-facts.js`. Composition lays each layer over it and keeps the
kernel's value of each, none is stamped for the browser to read, and the commands that
check a layer's own declarations name a change to one to its author
(`registry.layer.kernel_fact_advice`).
