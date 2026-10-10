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
  selections. A page's server runs the Leaf that started it against the runtime the
  page carries, and the render gate serves its probe modules from the Leaf running the
  command against the same runtime, so every page server — durable, temporary, and the
  gate's ephemeral one — compares this identity with its own payload's when it binds
  the page (`http.page_endpoint`, `layer.foreign_runtime`) and refuses a page carrying
  another Leaf's runtime, naming `leaf page init`. Served across the two, the page
  would break in the browser on every read: a renamed field in the state the server
  sends, or an export the page's runtime does not have. `fingerprint` cannot answer
  that question, because a package selection recorded beside it resolves against the
  project `page init` ran in and cannot be recomposed anywhere else. A page vendored
  before this identity existed records none and is refused the same way; `page init`
  records it again. The identity covers `assets/runtime/` alone: a contract change
  made only in the Python server, the boot `leaf.js`, the theme, or a package's
  widgets passes it. A checkout whose runtime modules were edited refuses every page
  vendored before the edit until each is re-vendored.
- `server` is the SHA-256 identity of the payload's Python serving code,
  `pyproject.toml`, `uv.lock`, and interpreter version. Initialization reads these inputs whether
  invoked directly or by a preview, so a server-only edit requires a new generation
  even when the installed browser files are unchanged. This identity decides
  re-vendoring; the runtime identity still owns the server's bind check.

HTTP responses also identify the serving incarnation in `Leaf-Server`. Every
document that runs the runtime, served or exported, carries an inline prepaint that
marks a startup failure before the module graph or stylesheet can fail, so the theme
gives back the readable fallback. A served page's inline bootstrap also supervises
the failure. It reloads when the server incarnation, layer generation, or website
release changes. A published page also reloads when its release-addressed probe
disappears. A rejected or unchanged re-vendor preserves its running server and
layer, so neither triggers a reload. Source files carry neither
script, and an export no supervisor.

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
