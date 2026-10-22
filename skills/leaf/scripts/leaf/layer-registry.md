# Layer composition and registry contract

`page init` vendors the theme, registry, widgets, and the browser modules and vendor
assets packages add into the page directory, composed on the order and merge grains in
`../../references/packages.md`, "Package contract"; `registry/layer.py` is the merge.
The browser runtime is not vendored: `leaf.js`, `runtime/` and the kernel's `vendor/`
modules come from the Leaf serving, checking or exporting the page
(`runtime_selection.py`). The page directory itself lives wherever the caller says —
conventionally ~/.local/state/leaf/pages/<slug>/ — and each revision captures its
authored content and vendored layer, so an approved version keeps what its user
approved, the content and the decisions on it, while the current Leaf's runtime draws
it. Re-running `page init` is the explicit re-vendor, which restarts a served page's
server when its installed layer, serving code or runtime changes
(`../../references/serving-pages.md`, "Re-vendoring"). One
transition covers start, stop, init, contract-bearing CLI writes, and preview reads.
Stop retains it through the server's release, so no operation can cross the old
process's contract.

A candidate layer validates its current vocabulary and the markup it renders;
historical actions and reports do not veto a replacement. Each newly admitted state
gesture records its operation and detail domain in `meaning.state`. Compatible
decisions continue to paint; values outside a revised domain and removed senders
remain historical-only. Immutable revisions retain their captured registries for
historical readings. Frozen thread markup has no independent implementation boundary,
so a candidate must still render that markup. Re-vendoring composes page-owned
declarations over the prospective layer before checking it. Initialization compares
the desired layer with every installed file it owns, including stale files in its
directories. Identical initialization preserves files, generation, provenance, and
the running server. Repairing installed files or changing the layer, package
selection, serving code or runtime requires a transition. `page init --dry-run`
reports that decision as `changed` without writing or stopping the service. Each layer
records its identities under `$layer`:

- `generation` is a fresh epoch for each transition, recorded in the registry. A
  served document names the generation of the revision it shows, state reports it,
  and event requests carry it; the server repeats it on contract responses, so an old
  or half-loaded tab refuses a foreign answer rather than letting a replacement server
  interpret or append its event. That tab reloads on top of the refusal only when its
  registry probe reports the new generation too, because a server running behind the
  document it served would hand back the same document. A revision's executable digest
  includes the generation, so a re-vendor gives an open tab a new document rather than
  a patch.
- `fingerprint` is the SHA-256 identity of the complete composed layer before that
  epoch is stamped. Identical theme, registry, widget, vendor, icon, and instructions
  bytes have the same fingerprint across repeated vendoring. `producer`
  records the Git commit and dirty bit when the payload came from a checkout or from
  Claude Code's Git-versioned plugin cache, and how old that commit is: `committed`,
  its committer date, where Git can read it, or `installed`, when the plugin cache
  copied it without `.git`, one update sweep after it landed. The page exposes that
  identity and its age in the floating panel's menu (Copy Leaf version), beside the
  Leaf serving the page where that is another; a press copies the full layer
  diagnostics. A harness can ask its running payload for the same source identity
  and date with `leaf --version`.
- `server` is the SHA-256 identity of the payload's Python serving code, the browser
  runtime it serves, `pyproject.toml`, and `uv.lock`. It excludes the interpreter
  version because a site builds pages on one Python release and serves them from a
  container on another. Initialization reads these inputs whether invoked directly or
  by a preview, so a server-only or runtime-only edit requires a new generation and a
  restart even when the vendored files are unchanged. This identity decides
  re-vendoring, never whether a page may be served or written.

These identities describe what the page vendored. The runtime a document executes is
named apart from them, by the identity `runtime_selection.py` gives the serving Leaf's
runtime. Where no website release names the runtime, a served document names it
(`data-lf-runtime-identity`), its resources are addressed under it, every answer names
the server's (`Leaf-Runtime`), and a tab names its own on every write. A tab refuses an
answer naming another runtime and the server refuses a write naming another, so a tab
from before a restart under an updated Leaf reloads rather than reading or writing
with code the server no longer runs.

HTTP responses also identify the serving incarnation in `Leaf-Server`. Every
document that runs the runtime, served or exported, carries an inline prepaint that
marks a startup failure before the module graph or stylesheet can fail, so the theme
gives back the readable fallback. A served page's inline bootstrap also supervises
the failure. It reloads when the server incarnation, layer generation, or website
release changes. A published page also reloads when its release-addressed probe
disappears. A fault that is the page's own, which no server fixes, it reports and
stops supervising. A rejected or unchanged re-vendor preserves its running server and
layer, so neither triggers a reload. Source files carry neither
script, and an export no supervisor.

## Page protocol

The kernel registry's `$events.protocol` numbers the contract between a page and any
Leaf that serves it or writes its log. A page keeps the layer it was vendored with,
while its runtime comes from the Leaf serving it, so the contract covers what crosses
Leaf versions: the kernel event records in the log and their ownership beside them;
what a page sends, which vendored package modules build through the runtime; the
declarations a vendored registry makes, such as its x-state verbs; the public package
API vendored modules call, `runtime/widget-api.js`, including what its readers such as
`readQueues`, `readObligations` and `readThreads` return; and the records Leaf keeps
outside a page. The served state is not part of it, since the runtime that reads it
comes from the Leaf that serves it. The page carries the number in the `$events` it
was vendored with, which no layer can change, and every page server — durable,
temporary, the gate's ephemeral one, and the website's — and the one append door
compare it with the running Leaf's own when they bind the page or admit an event
(`layer.incompatible_layer`), refusing another number. For a lower number the refusal
names `leaf page init`; for a higher one it names the newer Leaf that vendored the page,
since this Leaf does not re-vendor a page down.
The same reading refuses a layer whose `$keys` document an x- key this Leaf no longer
admits, since this Leaf would read the key's new name and drop what the page declares
under the old one; a key this Leaf added and the layer lacks refuses nothing.
Each reads the registry it would serve the page under: a snapshot's captured one, or
else the vendored layer. A revision is judged on the registry it captured, by both
readings (`layer.incompatible_revision`): a page re-vendored across a bump or a key's
rename keeps the revisions it saved before in its history, but the document server
serves none of them and the append door admits nothing made against one.

Any other Leaf at the same number serves and writes the page, so a plugin update
leaves open pages working: admission validates a kernel record against the running
Leaf's own `$events` (`registry.kernel`), so a field a newer Leaf writes passes on a
page an older one vendored. Bump the number when a page an older Leaf vendored at it
would break under this one: this Leaf refuses what a vendored module sends, a Leaf at
the number misreads an event another wrote into the log, this Leaf misreads a
declaration the vendored registry makes, or a vendored module breaks on the public
package API because a name it imports is gone or renamed or a value it reads changed
shape or meaning. A change to the served state needs no bump.

The browser build holds the schemas to this. It keeps `$events` and
`schema.VERB_SCHEMA`, the x-state verb a registry declares, as they last stood at the
current number (`build/browser/protocol-baseline.json`), and
`build/browser/protocol.mjs` compares each build's schemas with them keyword by
keyword (its header says how). It refuses a change to what a page sends that drops a
kind or a field at any depth, requires a new field, or tightens a constraint, such as a
narrower type, enum or constant, a changed pattern or a lower maximum; an event
record's change either way; and a verb's tightening, until the change takes what it
took or the number moves. The public package API has no schema there, so whoever
removes or renames a `widget-api.js` export, or changes what one returns, bumps the
number. `served_state/state.schema.json` still declares the served state and the
`/api/view` answer, for the generated types and the producer's tests, outside the
comparison.

The promise runs one way: an older Leaf serving a page a newer one vendored may refuse
a field it does not know. Every page vendored before a bump, and one vendored before the number was
declared, is refused until `leaf page init` re-vendors it. The first write command or
hook of the session holding the page runs that renewal itself (`vendoring.renew_layer`);
read commands leave its layer and service alone. A writer from another session does
not renew when the claim or its session lifecycle has a format it cannot read.

The number is also the only version of what Leaf keeps outside a page's log and
document: every JSON record in a page directory or in the state home, which every
installed Leaf on the machine shares (`state.Record`), and the composer's draft in
browser storage, which outlives a re-vendor. Each carries `leaf-<kind>/<number>`
in its `format`, and a reader at another format leaves it alone: it reads the record
as absent, or keeps a draft's words without its drawing. Retirement can inspect
a record's named page paths across formats (`state.named_pages`).
A record's number is its `since`, the protocol at which its own shape last changed,
so a bump for another change leaves a session's claim, its deliveries and a
page's port readable. A change to a record's shape that a reader at the same format
would misread sets its `since` to the current protocol, bumping the protocol first
where `since` already names it. The same build check holds this: the baseline keeps
each record's schema at its `since`, and fails a change at the same `since` that a
reader at either end would misread, or a `since` moved anywhere but the current
protocol. The composer's draft is held the same way: `$events.draft` declares its
schema and `since`, which its format names, and the baseline keeps that schema, with
the comment record's fields it refers to written in, beside the records.

The render gate's probes are outside the number: they come from the Leaf running the
check, as the runtime they import does. A vendored layer can still drift from a newer
runtime without a bump, such as a package widget that relies on runtime behavior an
update changed. While Leaf is in alpha that drift is accepted rather than bumped
(`AGENTS.md`, "Pages across Leaf updates"): `page check` names the page's Leaf beside
its own, with their dates, for the agent to judge.

## Composition stamps

Every composition writes these facts the browser reads instead of deriving
(`registry/layer.stamp_composition`):

- `$decisions`, each widget's deciding `x-state` verb and the member tags each of its
  outcomes retires;
- `$states`, each `x-state` verb's writer and the operation definition an admitted
  event records, which the browser compares a recorded definition with.

`page init` stamps them into the layer, and a page's composition stamps them again
over its own declarations, overwriting any declared `$decisions` or `$states`.

The kernel registry declares the rest of what both runtimes read, and the build
generates the browser's copy of each (`build/registry.mjs`), so none is stamped and
a layer that changes one is refused (`registry.layer.KERNEL_FACTS`):
`$marks`, each declaration a stylesheet reads with the attribute it is painted as,
which delivery paints into a page's document and the runtime into a message it
renders; `$names`, the widget and attribute name grammars; `$authored`, the page-wide
declarations an author writes for the runtime, whose values type the runtime's
readers; and the classifications on each `$events.kinds` entry (`registry.kernel`).
