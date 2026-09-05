# Layer composition and registry contract

`page init` vendors the runtime, theme, registry, widgets, and vendor assets into the
page directory. Leaf's kernel comes first, followed by the bundled default package,
any explicitly selected packages, the user's package (~/.config/leaf/), and the
project's package (./.leaf/). Theme stylesheets concatenate in that order, so a package
can override one token or rule without copying the defaults. Registry entries
merge by top-level name, with a later package replacing one complete entry rather
than deep-merging its schema; runtime, widget, and vendor files replace by path.
The page directory itself lives wherever the caller says —
conventionally ~/.local/state/leaf/pages/<slug>/ — and is self-contained,
so an approved version can't change under its user; re-running `page init`
is the explicit re-vendor, noted in the next stamped version's changelog. A served page
is first stopped, which disables its desired service and waits for the process
and every accepted connection to retire. After re-vendoring, `server start`
restores its URL and lifetime; its status needs no maintenance copy. One
transition covers start, stop, init, contract-bearing CLI writes, and preview
reads. Stop retains it through the server's release, so no operation can cross
the old process's contract.

The registry is shared by the JS runtime, the POST and re-vendor action gates,
`leaf version check` and thread-markup validation, the passage reader
`leaf comment` anchors through, and the selective queries the agent runs. Each
successful init records two deliberately different identities under `$layer`:

- `generation` is a fresh epoch embedded in both leaf.js and the registry. State
  reports it and event requests carry it; the server repeats it on contract
  responses, so an old or half-loaded tab reloads before a replacement server can
  interpret or append its event.
- `fingerprint` is the SHA-256 identity of the complete composed layer before that
  epoch is stamped. Identical runtime, theme, registry, widget, vendor, icon, and
  guidance bytes have the same fingerprint across repeated vendoring. `producer`
  records the Git commit and dirty bit when the payload came from a checkout.

HTTP responses also identify the serving incarnation in `Leaf-Server`. A served
page's inline, CSP-hashed bootstrap supervises startup before the module graph
or stylesheet can fail. After a startup failure it reloads only when the server
incarnation or layer generation changes. This includes a rejected re-vendor:
its layer stays frozen, but the restarted server can finish a formerly interrupted
load. Source files and standalone exports carry no startup supervisor.

`registry.json` remains the source of truth for the current custom vocabulary and
its explanations; this contract does not mirror that inventory.

The append transaction records state coordinates and direct dependencies in an
action or report's `meaning`. Identity-bearing fields come from the declared fold
unit and attribute-set or position record. Additional string or string-array
fields must be named in `references`; arbitrary detail strings carry no identity.
The current document still supplies containment when reading those dependencies.

A state verb that creates authored children declares `creates: {field, child}`.
The optional detail field is the canonical map from generated element ids to their
first authored words, and `child` names their exact tag. The server snapshots the
map's sorted keys in `generated`. Historical folds read that durable ownership;
source continuity and word validation read the declaration.
