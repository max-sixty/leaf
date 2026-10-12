# Layer composition and registry contract

`page init` vendors the runtime, theme, registry, widgets, and vendor assets into the
page directory, composed on the order and merge grains in
`../../references/packages.md`, "Package contract"; `registry/layer.py` is the merge.
The page directory itself lives wherever the caller says —
conventionally ~/.local/state/leaf/pages/<slug>/ — and is self-contained,
so an approved version can't change under its user; re-running `page init`
is the explicit re-vendor, which restarts a served page's server when its installed
layer or serving code changes
(`../../references/serving-pages.md`, "Re-vendoring and layer epochs"). One
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
selection, or serving code requires a transition. `page init --dry-run` reports
that decision as `changed` without writing or stopping the service. Each layer
records its identities under `$layer`:

- `generation` is a fresh epoch for each transition, embedded in both `runtime/layer-generation.js` and the
  registry. State reports it and event requests carry it; the server repeats it on
  contract responses, so an old or half-loaded tab refuses a foreign answer rather
  than letting a replacement server interpret or append its event. That tab reloads
  on top of the refusal only when its registry probe reports the new generation too,
  because a server running behind the document it served would hand back the same
  document.
- `fingerprint` is the SHA-256 identity of the complete composed layer before that
  epoch is stamped. Identical runtime, theme, registry, widget, vendor, icon, and
  instructions bytes have the same fingerprint across repeated vendoring. `producer`
  records the Git commit and dirty bit when the payload came from a checkout or from
  Claude Code's Git-versioned plugin cache, and how old that commit is: `committed`,
  its committer date, where Git can read it, or `installed`, when the plugin cache
  copied it without `.git`, one update sweep after it landed. The page exposes that
  identity and its age in its low-frequency banner controls; a press copies the full
  layer diagnostics. A harness can ask its running payload for the same source identity
  and date with `leaf --version`.
- `runtime` is the SHA-256 identity of the kernel runtime modules the payload vendored
  from, read from its own `assets/runtime/` rather than recomposed from the page's
  selections. The render gate serves its probe modules from the Leaf running the
  command, and they import the page's runtime modules by name, so the gate alone
  requires this exact identity (`layer.foreign_runtime`) and refuses another, naming
  `leaf page init`. `fingerprint` cannot answer that question, because a package
  selection recorded beside it resolves against the project `page init` ran in and
  cannot be recomposed anywhere else.
- `server` is the SHA-256 identity of the payload's Python serving code,
  `pyproject.toml`, and `uv.lock`. It excludes the interpreter version because a site
  builds pages on one Python release and serves them from a container on another.
  Initialization reads these inputs whether invoked directly or by a preview,
  so a server-only edit requires a new generation
  even when the installed browser files are unchanged. This identity decides
  re-vendoring, never whether a page may be served or written.

HTTP responses also identify the serving incarnation in `Leaf-Server`. Every
document that runs the runtime, served or exported, carries an inline prepaint that
marks a startup failure before the module graph or stylesheet can fail, so the theme
gives back the readable fallback. A served page's inline bootstrap also supervises
the failure. It reloads when the server incarnation, layer generation, or website
release changes. A published page also reloads when its release-addressed probe
disappears. A rejected or unchanged re-vendor preserves its running server and
layer, so neither triggers a reload. Source files carry neither
script, and an export no supervisor.

## Page protocol

The kernel registry's `$events.protocol` numbers the contract between a page and any
Leaf that serves it or writes its log: the kernel event records and their ownership
beside it, the reading the server serves the page's runtime, and each runtime module
the server relies on. The page carries the number in the `$events` it was vendored
with, which no layer can change, and every page server — durable, temporary, the
gate's ephemeral one, and the website's — and the one append door compare it with
the running Leaf's own when they bind the page or admit an event
(`layer.incompatible_layer`), refusing another number and naming `leaf page init`.
Each reads the registry it would serve the page under: a snapshot's captured one, or
else the vendored layer.

Any other Leaf at the same number serves and writes the page, so a plugin update
leaves open pages working: admission validates a kernel record against the running
Leaf's own `$events` (`registry.kernel`), so a field a newer Leaf writes passes on a
page an older one vendored. Bump the number when a page an older Leaf vendored at it
would break under this one: the served state, a runtime module the server relies on,
or an event drops, renames or changes the meaning of something the other side reads,
or a field the page's runtime sends becomes required, as a new drawing `format` does.
Adding a field or kind the older code ignores needs no bump. The promise runs one
way: an older Leaf serving a page a newer one vendored may refuse a field it does not
know. Every page vendored before a bump, and one vendored before the number was
declared, is refused until `leaf page init` re-vendors it.

## Composition stamps

Every composition writes two facts the browser reads instead of deriving
(`registry/layer.stamp_composition`):

- `$decisions`, each widget's deciding `x-state` verb and the member tags each of its
  outcomes retires;
- `$marks`, each declaration a stylesheet reads, with the attribute it is painted as,
  the attribute an occurrence overrides it with, and whether it holds in a thread
  message, and whether an idiom may declare it (`schema.DECLARED_MARKS`).

`page init` stamps them into the layer, and a page's composition stamps them again
over its own declarations, overwriting any declared `$decisions` or `$marks`.
Delivery paints a page document's marks from the same table.
