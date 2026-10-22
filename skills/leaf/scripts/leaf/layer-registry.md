# Layer composition and registry contract

`page init` vendors the runtime, theme, registry, widgets and vendor assets into the
page directory, composed in the order and at the merge grains of
`../../references/packages.md`, "Package contract"; `registry/layer.py` is the merge.
The page directory is self-contained, so an approved version can't change under its
user. Re-running `page init` is the explicit re-vendor
(`../../references/serving-pages.md`, "Re-vendoring"). `vendoring.cmd_init` decides
whether it changes anything, and `page init --dry-run` reports that decision as
`changed` without writing or stopping the server.

A candidate layer must validate its current vocabulary and every markup it renders,
frozen thread markup included, after page-owned declarations are composed over it.
Historical actions and reports never veto a layer. Each admitted state gesture
records its operation and detail domain in `meaning.state`, so a decision the new
domain still accepts keeps painting, and one outside it, or whose sender is gone,
stays in history only. Each revision keeps the registry it captured for historical
readings.

Each layer records its identities under `$layer`:

- `generation`, a fresh epoch whenever the fingerprint, the server identity or the
  package selection changes. It is embedded in `runtime/layer-generation.js` and the
  registry, event requests carry it, and contract responses repeat it, so a tab
  holding an old or half-loaded layer refuses a foreign answer rather than letting a
  replacement server interpret its event. The tab reloads only once its registry
  probe also reports the new generation, since a server running behind the document
  it served would hand back the same document.
- `fingerprint`, the SHA-256 of the composed layer before the generation is stamped,
  so identical bytes give the same fingerprint on every vendoring. `producer` records
  the Git commit, the dirty bit, and the commit's age: `committed`, its committer
  date, or `installed` where a plugin cache copied the tree without `.git`. The
  panel's menu (Copy Leaf version) and `leaf --version` show this identity.
- `server`, the SHA-256 of the payload's Python serving code, `pyproject.toml` and
  `uv.lock`, without the interpreter version, since the site builds pages on one
  Python and serves them on another. A server-only edit therefore makes a new
  generation. This identity decides re-vendoring, never whether a page may be served
  or written.

A served page's bootstrap (`runtime/bootstrap.js`) reloads the tab when the server
incarnation (`Leaf-Server`), the layer generation or the website release changes. A
rejected or unchanged re-vendor keeps the server and the generation, so open tabs
don't reload.

## Page protocol

The kernel registry's `$events.protocol` numbers the contract between a page and any
Leaf that serves it or writes its log: the kernel event records and their ownership,
the state the server serves the page's runtime, and each runtime module the server
relies on. A page carries the number in the `$events` it was vendored with, which no
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

Bump the number when a page an older Leaf vendored at it would break under this one:

- this Leaf refuses something the page's runtime sends;
- a Leaf at the number misreads an event another wrote into the log;
- a runtime module the server relies on drops, renames or changes the meaning of
  something the server reads;
- the page's runtime mishandles what this Leaf now serves, because a field it reads is
  gone, renamed, retyped or means something else, or a value it reads reaches code
  that doesn't handle it.

A served change no such runtime reads needs no bump. Serving `null` as an approval
obligation's `prompt.target` breaks no page, for example, since the runtime reads the
target only for a widget's obligation.

The browser build holds the schemas to this. `build/browser/protocol-baseline.json`
keeps `$events`, `served_state/state.schema.json`, `schema.VERB_SCHEMA`, each
`state.Record` schema and the composer's draft as they stood at the current number,
and `build/browser/protocol.mjs` compares each build against it (its header says in
which direction for each schema). It refuses a change to what a page sends or to an
event record until the change takes what it took or the number moves. A change to
the served state it only names, because a runtime reads just some of the served
fields, and the build refuses it until the author bumps the number or runs
`pnpm run build:browser --accept-served`. Before accepting, check each reader of a
named field in the runtime and packages, as they stand now and at every commit since
the number was set (`git log -S` over that range finds a reader a later commit
removed), and name the readers checked in the commit.

The number is also the only version of what Leaf keeps outside a page's log and
document: every JSON record in a page directory or the state home (`state.Record`)
and the composer's draft in browser storage (`$events.draft`). Each carries
`leaf-<kind>/<since>` in its `format`, where `since` is the protocol at which that
record's own shape last changed, so a bump for another change leaves claims,
deliveries and ports readable. A shape change that a reader at the same format would
misread sets `since` to the current protocol, bumping the protocol first where `since`
already names it. The build fails a change at the same `since` that a reader at
either end would misread, and a `since` moved anywhere but the current protocol. A
reader at another format treats a record as absent, and keeps a draft's words
without its drawing.

The render gate's probes are outside the number. They come from the Leaf running the
check and import `check-api.js` and `widget-api.js` from the page's runtime, so a
probe that imports a newer name fails on a page vendored earlier, and the gate
refuses naming the re-vendor. While Leaf is in alpha that drift is accepted rather
than bumped (`AGENTS.md`, "Pages across Leaf updates").

## Composition stamps

Every composition, `page init`'s layer and a page's own declarations over it, stamps
the facts the browser reads rather than derives (`registry/layer.stamp_composition`),
overwriting any a layer declared: `$decisions`, each widget's deciding `x-state` verb
and the member tags each of its outcomes retires, and `$states`, each verb's writer
and the operation definition an admitted event records.

The kernel registry declares the other facts both runtimes read
(`registry.layer.KERNEL_FACTS`, described in `registry/kernel.py`'s header, and the
classifications on each `$events.kinds` entry). The build generates the browser's
copy of each (`build/registry.mjs`), so none is stamped, and a layer that changes
one is refused.
