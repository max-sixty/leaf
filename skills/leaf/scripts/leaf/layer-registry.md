# Layer composition and registry contract

`page init` vendors the runtime, theme, registry, widgets, and vendor assets into the
page directory, composed on the order and merge grains in
`../../references/packages.md`, "Package contract"; `registry/layer.py` is the merge.
The page directory itself lives wherever the caller says —
conventionally ~/.local/state/leaf/pages/<slug>/ — and is self-contained,
so an approved version can't change under its user; re-running `page init`
is the explicit re-vendor, on the sequence in `../../references/serving-pages.md`,
"Re-vendoring and layer epochs". One transition covers start, stop, init,
contract-bearing CLI writes, and preview reads. Stop retains it through the server's
release, so no operation can cross the old process's contract.

A candidate layer must retain every page action or report whose sender it retains,
including superseded predecessors that a later undo can expose. It must also retain
all frozen thread markup and the actions and requests sent from it, because that
document has no revision boundary. Page events whose senders the candidate removes are
historical-only and remain interpretable through the registry captured with their
immutable revisions. Re-vendoring composes page-owned declarations over the
prospective layer before running this same candidate check. Each successful init
records three deliberately different identities under `$layer`:

- `generation` is a fresh epoch embedded in both `runtime/layer-client.js` and the
  registry. State reports it and event requests carry it; the server repeats it on
  contract responses, so an old or half-loaded tab refuses a foreign answer rather
  than letting a replacement server interpret or append its event. That tab reloads
  on top of the refusal only when its registry probe reports the new generation too,
  because a server running behind the document it served would hand back the same
  document.
- `fingerprint` is the SHA-256 identity of the complete composed layer before that
  epoch is stamped. Identical runtime, theme, registry, widget, vendor, icon, and
  guidance bytes have the same fingerprint across repeated vendoring. `producer`
  records the Git commit and dirty bit when the payload came from a checkout or from
  Claude Code's Git-versioned plugin cache. The page exposes that identity in its
  low-frequency banner controls; a press copies the full layer diagnostics. A host can
  ask its running payload for the same source identity with `leaf --version`.
- `runtime` is the SHA-256 identity of the kernel runtime modules the payload vendored
  from, read from its own `assets/runtime/` rather than recomposed from the page's
  selections. It is the half the render gate's probe modules import: the gate serves
  those probes from the Leaf running the command and the runtime those probes import
  from the page, so the ephemeral server compares this identity and refuses a page
  carrying another Leaf's runtime, rather than letting the mismatch arrive in the
  browser as an export the page's runtime does not have. `fingerprint` cannot answer
  that question, because a package selection recorded beside it resolves against the
  project `page init` ran in and cannot be recomposed anywhere else. A page vendored
  before this identity existed records none and is refused the same way; `page init`
  records it again.

HTTP responses also identify the serving incarnation in `Leaf-Server`. A served
page's inline, nonce-authorized bootstrap supervises startup before the module graph
or stylesheet can fail. After a startup failure it reloads when the server
incarnation, layer generation, or website release changes. A published page also
reloads when its release-addressed probe disappears. This includes a rejected
re-vendor: its layer stays frozen, but the restarted server can finish a formerly
interrupted load. Source files and standalone exports carry no startup supervisor.

`registry.json` remains the source of truth for the current custom vocabulary and
its explanations; this contract does not mirror that inventory.

The append transaction records the fold unit and direct dependencies in an action or
report's `meaning`. Identity-bearing detail fields come from the declared fold unit
and attribute-set or position record; arbitrary detail strings carry no identity.
