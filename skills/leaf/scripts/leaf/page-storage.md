# Page storage

## Files

The author writes `index.html` and the files under `page/`; Leaf writes everything
else. A page directory holds:

- `index.html` — the author's mutable candidate. The server validates it before
  activating it and never serves it directly. An invalid save leaves the previous
  revision live and reports its diagnostic in page state and the browser.
- `revisions/rN-H.html` — an immutable valid save: N is activation order and H the
  first 16 hex characters of its artifact-manifest digest. The sibling `rN-H/` holds
  `index.html`, `manifest.json`, the registry, and every dependency the revision
  delivers, made durable before the `.html` marker appears
  (`revision_artifact.py`). Identical inputs reuse a revision.
- `/versions/vN.html` — virtual. Each `note` event maps a version to a revision, which
  the server renders at the version's URL, so a stamped version never moves. A static
  site build may write these responses out as disposable output, never as authority.
- `leaf.js` — the browser entry.
- `theme.css` — tokens, element styles, class idioms, and widget CSS.
- `shadow.css` — the rules declared shadow trees also need; `theme.css` carries them
  too, ahead of each package's own rules.
- `registry.json` — the composed widget schemas and `$layer`
  ([layer-registry.md](layer-registry.md)).
- `guidance/` — package guidance by audience, files of one name concatenated in
  package order; `leaf page guidance` reads it.
- `icon.svg` — the tab icon; its `lf-tone` element follows the banner's status colour.
- `runtime/` — the browser runtime, with the public `widget-api.js`.
- `widgets/` — one ES module per upgraded widget.
- `vendor/` — third-party assets, the kernel's and any selected package's.
- `page/` — the author's page-specific modules, styles, assets, `registry.json`
  declarations, and `widgets/`. They are candidate inputs: delivery reads the copies a
  revision captured.
- `media/` — content-addressed images shared by every revision, written by
  `leaf page media` and `/api/media` (`media.py`). A name, minted by `media.media_name`,
  always identifies the same bytes; `page check` and the agent's message doors refuse
  any other name under `/media/`. A revision records the media its document names,
  but every host serves media at the page root. Nothing deletes media: an abandoned
  draft can leave an unreferenced image, and proving it unreferenced would mean
  reading every revision and event.
- `events.jsonl` — the append-only event log ([events.md](events.md)).
- `interactions.jsonl` — a best-effort diagnostic trace of server requests and browser
  input, refused requests included. Nothing reads it but a person following the file
  (`tail -F`); it never enters page state or acknowledgement and is never served. The
  server appends each request's method, path without query, status, and duration,
  `/api/interaction` appends each tab's batches, and a sample page's batches go to its
  parent's trace. A
  resent record repeats its `(session, sequence)`; a large one arrives as
  `interaction_part` rows whose `json` fields concatenate in `part` order; a dropped
  one leaves a sequence gap or an `interaction_omitted` row
  (`runtime/interaction-log.js`).
- `data.json` — the contract each external-data source id was first set under
  (`data.py`).
- `data/` — `<source>.json`, each source's current value. Any process may rewrite one;
  every reading validates it against its recorded contract. `/api/deferred` serves
  deferred record fields from these same files.
- `status.json` — work declarations, observed activity, and reply bindings, read
  through `service.read_status`, which treats a missing file as no declaration.
  [session-lifetime.md](session-lifetime.md) owns their writers and lifetimes, and
  `thread.py` the reply bindings.
- `waiter.lock` — the wait lease of a `leaf wait` run from a bare shell, present only
  while held; a host session's is `<state-home>/sessions/<session>.wait`.
- `viewed.json` — when a visible tab last showed the page, renewed by the server
  (`http.py`); absent until first viewed.
- `cursor.json` — the acknowledged position in the event log
  ([session-lifetime.md](session-lifetime.md)).
- `preview.json` — the identity `leaf-dev preview` gives a preview, handed to the page
  whole. Its presence exempts the page from the handoff's watcher guard.
- `service.json` — the server's address, enabled state, lifetime, and runtime
  provenance, written by `hosting.py`; the lifetime rule is
  [session-lifetime.md, "Lifetime"](session-lifetime.md#lifetime). While `page init`
  holds a served page down to re-vendor it, a `restart` mark says to start it again;
  any other stop meanwhile clears it, and the page stays stopped. The URL's access key
  belongs to the state home.
- `server.lock` — the running server's lease; a stop waits for its release, after the
  server has closed its sockets.

The page lock is the directory itself: `leases.page_locked` flocks it to serialize
service changes, re-vendoring, contract-bearing writes, and `page check`, so the lock
writes nothing and ends with the page.

Two stores sit outside page directories, in the state home:

- `<state-home>/claims/` — one claim per page, removed by the first scan that finds
  its page directory gone (`service.claim_records`).
  [session-lifetime.md](session-lifetime.md) owns claims.
- `<state-home>/deliveries/<id>.json` — immutable deliveries. One delivery can carry
  batches from several pages and must read the same in every host, so it lives
  outside any of them. Acknowledgement archives the mutable delivery records
  beside it, never the delivery `leaf delivery read <id>` reads.

## Revision delivery

The live root serves the active revision, and revision and version addresses go
through the same delivery; all three name the page root as canonical. The revision
manifest's executable and widget digests decide whether an open tab replaces its
document or keeps its widgets (`revision_artifact.py`).

## Page state

`leaf page state` reads these files on demand:

- `layer`, shared with `/api/state`: the vendored `$layer`.
- `source`: `index.html`, whether it is live, and any validation error.
- `active.file`: the revision the live root shows, once one exists, and
  `active.executable`, its executable digest, which delivery writes as
  `<meta name="lf-executable">` for `../../assets/runtime/version.js`.
- `data`: the contract file, the value directory, and any source whose value fails
  its contract; `data_bindings` names each source and the widgets reading it.
- `event_seq`: the last event folded into the reading, for
  `leaf page events --after`; it is not the acknowledgement cursor.

`leaf page state <page> <id>` narrows the reading to what the id names. A message, or
a widget frozen into one, names its thread: that thread's messages, bounded by
`--after` and `--limit`, each with its frozen markup under `content`
(`construction.py`), since that markup has no file of its own. A page widget names
its element, the state and updates resting on it, the Asks it holds or answers, and
the workflows it is the subject of. Page ids and event ids share this address space,
so `page check` refuses an authored id shaped like an event id. What the agent reads
alongside is `../../references/authoring-revisions.md`, "Read before editing".
