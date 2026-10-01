# Layer composition and registry contract

`page init` composes the kernel and the selected packages into one layer and vendors
it into the page directory: runtime, theme, registry, widgets, and vendor assets.
`registry/layer.py` is the merge, on the order and grains of
`../../references/packages.md`, "Package contract". A page serves only what it
carries, so a version the user approved cannot change under them. Re-running
`page init` is the only re-vendor; `../../references/serving-pages.md`,
"Re-vendoring and layer epochs", says how it restarts a served page. It holds the page
lock (`page-storage.md`, "Files") throughout, so no other operation runs against the
old contract and the new one at once.

A candidate layer must keep what the log still uses: every page action or report
whose sender widget it keeps, superseded ones included, since an undo can expose
them; and all frozen thread markup and the actions sent from it, since thread markup
has no revision boundary. A page event whose sender the candidate removes is read
through the registry captured with its revision. A re-vendor composes the page's own
declarations over the candidate before this check (`validation/compatibility.py`).

## `$layer`

Each successful init records under `$layer`:

- `generation`, a fresh epoch embedded in `runtime/layer-client.js` and the registry.
  State reports it, event requests carry it, and the server repeats it on contract
  responses, so a tab loaded from an older layer refuses the answer rather than have
  the new server interpret its event. The tab reloads only once its registry probe
  also reports the new generation, since a server running behind the document it
  served would hand back the same document.
- `fingerprint`, the SHA-256 of the complete composed layer before the epoch is
  stamped, so the same bytes always vendor to the same fingerprint.
- `runtime`, the SHA-256 of the kernel's `assets/runtime/` modules in the vendoring
  payload. Every page server, the render gate's included, compares it with its own
  payload's when it binds a page (`layer.foreign_runtime`) and refuses a mismatch,
  naming `leaf page init`: a server and a browser runtime from different payloads break
  the page on every read. `fingerprint` cannot serve this check, because its package
  selections resolve only in the project `page init` ran in. A contract change made
  only in the Python server, `leaf.js`, the theme, or a package passes this check, and
  editing a checkout's runtime refuses every page vendored before the edit.
- `packages`, the selections as recorded.
- `producer`, the payload's Git commit and dirty bit, and its age: `committed`, the
  commit date, or `installed`, when a plugin cache copied it without `.git`. The
  banner shows it, and `leaf --version` reports the same for the running payload.

## Startup

Every HTTP response names its server process in `Leaf-Server`. A served page's inline
bootstrap (`runtime/bootstrap.js`) runs before the module graph or stylesheet can
fail. After a failed start it reloads once the server process, the layer generation,
or the website release changes, or, on a published page, once its release-addressed
probe disappears. A refused re-vendor leaves the layer as it was, but the restarted
server can finish a load that failed earlier. Source files and standalone exports
carry no bootstrap.

## Composition stamps

Every composition writes two facts the browser reads instead of deriving
(`registry/layer.stamp_composition`):

- `$decisions`, each widget's deciding `x-state` verb and the member tags each of its
  outcomes retires;
- `$marks`, each declaration a stylesheet reads, with the attribute it is painted as,
  the attribute an occurrence overrides it with, and whether it holds in a thread
  message (`schema.DECLARED_MARKS`).

`page init` stamps them into the layer, and a page's composition stamps them again
over its own declarations, overwriting any declared `$decisions` or `$marks`.
Delivery paints a page document's marks from the same table.
