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

`registry.json` remains the source of truth for the current custom vocabulary and
its explanations; this contract does not mirror that inventory.

Within a registry-validated action detail, a string or list of strings may point
at existing ids inside the sending widget. A state verb that creates authored
children declares `creates: {field, child}`. The optional detail field is the
canonical map from generated element ids to their first authored words, and
`child` names their exact tag. The browser snapshots the map's sorted keys in
the action's `generated` field. Registry-free historical folds read that snapshot;
source continuity and word validation read the declaration, so an arbitrary
mapping is never inferred to contain ids.
