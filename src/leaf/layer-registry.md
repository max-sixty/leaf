# Layer composition and registry contract

`page init` vendors the theme, registry, widgets, and the browser modules and vendor
assets packages add into the page directory, composed in the order and at the merge
grains of `../../skills/leaf/references/packages.md`, "Package contract";
`registry/layer.py` is the merge. The browser runtime is not vendored: `leaf.js`,
`runtime/` and the kernel's `vendor/` modules come from the Leaf serving, checking or
exporting the page (`runtime_selection.py`). Each revision captures its authored
content and vendored layer, so an approved version keeps what its user approved while
the current Leaf's runtime draws it. Re-running `page init` is the explicit re-vendor,
which restarts a served page's server when its layer, serving code or runtime changes
(`../../skills/leaf/references/serving-pages.md`, "Re-vendoring"). `vendoring.cmd_init`
decides whether it changes anything, and `page init --dry-run` reports that decision as
`changed` without writing or stopping the server. The page lock serializes it with
service changes and contract-bearing writes (`page-storage.md`).

A candidate layer must validate its current vocabulary and every markup it renders,
frozen thread markup included, after page-owned declarations are composed over it.
Historical actions and reports never veto a layer. Each admitted state gesture
records its operation and detail domain in `meaning.state`, so a decision the new
domain still accepts keeps painting, and one outside it, or whose sender is gone,
stays in history only. Each revision keeps the registry it captured for historical
readings.

Each layer records its identities under `$layer`:

- `packages` records content-package selections. `theme` is the separately selected
  personal theme, `{name, source}` with `source` explicit or default, or null.
  The theme composes after the content packages. Re-vendoring preserves the captured
  choice until `--theme` replaces it or `--no-theme` / `--no-packages` clears it. User catalogue
  changes affect new pages; `themes.py` owns selection and `package-themes.md`
  documents its authoring interface.

- `generation`, a fresh epoch whenever the fingerprint, the server identity or the
  package selection changes. It is recorded in the registry, a served document names
  the generation of the revision it shows, event requests carry it, and contract
  responses repeat it, so a tab holding an old or half-loaded layer refuses a foreign
  answer rather than letting a replacement server interpret its event. The tab reloads
  only once its registry probe also reports the new generation, since a server running
  behind the document it served would hand back the same document. A revision's
  executable digest includes the generation, so a re-vendor gives an open tab a new
  document rather than a patch.
- `fingerprint`, the SHA-256 of the composed layer before the generation is stamped,
  so identical bytes give the same fingerprint on every vendoring. `producer` records
  the Git commit, the dirty bit, and the commit's age: `committed`, its committer
  date, or `installed` where a plugin cache copied the tree without `.git`. The
  panel's menu (Copy Leaf version) shows this identity, beside the Leaf serving the page
  where that is another, and `leaf --version` prints it.
- `server`, the SHA-256 of the payload's Python serving code, the browser runtime it
  serves, `pyproject.toml` and `uv.lock`, without the interpreter version, since the
  site builds pages on one Python and serves them on another. A server-only or
  runtime-only edit therefore makes a new generation and a restart. This identity
  decides re-vendoring, never whether a page may be served or written.

The runtime a document executes is named apart from these identities, by the one
`runtime_selection.py` gives the serving Leaf's runtime. Where no website release names
the runtime, a served document names it (`data-lf-runtime-identity`), its resources are
addressed under it, every answer names the server's (`Leaf-Runtime`), and a tab names
its own on every write. Each side refuses the other's message naming another runtime,
so a tab from before a restart under an updated Leaf reloads rather than reading or
writing with code the server no longer runs.

A served page's bootstrap (`runtime/bootstrap.js`) reloads the tab when the server
incarnation (`Leaf-Server`), the layer generation or the website release changes. A
rejected or unchanged re-vendor keeps the server and the generation, so open tabs
don't reload.

## Page protocol

The kernel registry's `$events.protocol` numbers the contract between a page and any
Leaf that serves it or writes its log. A page keeps the layer it was vendored with,
while its runtime comes from the Leaf serving it, so the contract covers what crosses
Leaf versions: the kernel event records and their ownership; what a page sends, which
vendored package modules build through the runtime; the declarations a vendored
registry makes, such as its x-state verbs; the public package API vendored modules
call, `runtime/widget-api.js`, including what its readers such as `readObligations`
return; and the records Leaf keeps outside a page. The served state is not part of it,
since the runtime that reads it comes from the Leaf that serves it. A page carries the number in the `$events` it was vendored with, which no
layer can change. Every page server and the append door refuse a page, or a revision,
vendored at another number, or whose `$keys` document an x- key this Leaf no longer
admits (`layer.incompatible_layer` and `layer.incompatible_revision` say what each
refusal names). A page at a lower number is re-vendored by the session holding it, at
its first write command or hook naming the page (`vendoring.renew_layer`); read
commands leave its layer and server alone. No Leaf re-vendors a page down.

Any Leaf at the page's number serves and writes it, so a plugin update leaves open
pages working. Admission validates a kernel record against the running Leaf's own
`$events` (`registry.kernel`), so a field a newer Leaf writes passes on a page an
older one vendored. The promise runs one way: an older Leaf may refuse a field it
does not know.

"Any Leaf at the page's number" is per process, and one session can run two. Claude
Code keeps a session on the plugin copy it loaded after its marketplace sweep installs
an update, until `/reload-plugins` or a restart, and a worktree's `bin/leaf` can
re-vendor a page the session holds past that copy. So the copy the session loaded
hands each hook, its watch and its bare `leaf` commands to the session's delivering
Leaf: the checkout that last re-vendored one of its pages, or a preview's, while it
exists, and otherwise the copy Claude Code installed since (`session_runtime.py`). An
update then reaches a session at its next hook; `hooks.json` and the hooks module,
which Claude Code reads as it loads the plugin, still wait for a reload. Where a
watch still can't read a page, as one started before this hand-off existed, its lease
names the older protocol it speaks, so a newer Leaf reads it as no watch and admission
nudges the session (`leases.wait_is_live`).

Bump the number when a page an older Leaf vendored at it would break under this one:

- this Leaf refuses something a vendored module sends;
- a Leaf at the number misreads an event another wrote into the log;
- this Leaf misreads a declaration the vendored registry makes;
- a vendored module breaks on the public package API, because a name it imports is
  gone or renamed, or a value it reads changed shape or meaning.

Additive public APIs and changes to the served state keep the number, since neither
breaks a page vendored before the change.

The browser build holds the schemas to this. `build/browser/protocol-baseline.json`
keeps `$events`, `schema.VERB_SCHEMA`, each `state.Record` schema and the composer's
draft as they stood at the current number, and `build/browser/protocol.mjs` compares
each build against it (its header says in which direction for each schema). It refuses
a change to what a page sends, to an event record, or a verb's tightening, until the
change takes what it took or the number moves. The public package API has no schema
there, so whoever removes or renames a `widget-api.js` export, or changes what one
returns incompatibly, bumps the number. A passing comparison doesn't judge that, nor
whether a bump chosen by hand was needed.
`served_state/state.schema.json` declares the served state and the `/api/view` answer
for the generated types and the producer's tests, outside the comparison.

The number is also the only version of what Leaf keeps outside a page's log and
document: every JSON record in a page directory or the state home (`state.Record`)
and the composer's draft in browser storage (`$events.draft`). Each carries
`leaf-<kind>/<since>` in its `format`, where `since` is the protocol at which that
record's own shape last changed, so a bump for another change leaves claims,
deliveries and ports readable. A new record kind starts at the current protocol
without a bump, since earlier Leaves have no reader for it. A shape change that a reader at the same format would
misread sets `since` to the current protocol, bumping the protocol first where `since`
already names it. The build fails a change at the same `since` that a reader at
either end would misread, and a `since` moved anywhere but the current protocol. A
reader at another format treats a record as absent.

The render gate's probes are outside the number: they come from the Leaf running the
check, as the runtime they import does. A vendored layer can still drift from a newer
runtime without a bump, as when a package widget relies on runtime behavior an update
changed. While Leaf is in alpha that drift is accepted rather than bumped
(`AGENTS.md`, "Pages across Leaf updates").

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
