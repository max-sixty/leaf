# Page storage

## Files

The author writes `index.html` and the `page/` candidate inputs. Leaf owns every other
file below, in the page directory or the state home. Each entry names the module that
owns it, whose header holds the rest of its contract.

Each JSON record below is a `state.Record`, declared once beside its owning module,
whose functions are its only writers. Its `format` versions it
([layer-registry.md](layer-registry.md), "Page protocol"), and each shape is kept under
the name below with its `since` before the suffix, as `drafts@51.json`, so a Leaf of
one shape never reads or replaces another's. A state-home record whose pages are gone
is removed by whichever Leaf of its shape next lists it (`state.retire_if_gone`).

- `index.html` — the author's mutable document. The server validates it before
  activation and never serves it directly. An invalid save creates no revision, leaves
  the previous revision live, and shows its diagnostic in page state and the browser.

- `revisions/rN-H.html` — the marker of one valid save, where N is the activation order
  and H the first 16 hex characters of the artifact manifest's digest. Its sibling
  `revisions/rN-H/` holds everything the page's author owns in that revision, durable
  before the marker appears: the document, its own declarations and modules, its
  media references, and the layer selection its manifest names. The serving Leaf
  supplies the runtime and the layer (`runtime_selection.py`). Identical artifacts
  reuse a revision, and a bundle hard-links the resources whose bytes the previous
  revision captured, so no file is written in place (`revision_artifact.py`).

- `/versions/v1.html…` — virtual addresses. Each `note` event maps a version to its
  immutable revision, which the server renders at the version's URL, so a pinned
  version never moves as later saves go live. A static-site build may write these
  responses out as disposable delivery output, never an authority.

- `layer.json` — the packages the page selects and its generation, in a `format`
  that names its page protocol (`registry.storage.LAYER`,
  [layer-registry.md](layer-registry.md)).
  Every Leaf that reads the page composes its registry, theme, instructions, widgets
  and package modules from it; none of them is a file in the page.

- `packages/<name>/` — the page's copy of each package it selects by path, which
  `layer.json` names as `./packages/<name>` (`vendoring`). A path names a directory
  relative to where `page init` ran, so init copies the package's layer files here,
  and every reader composes the copy. The next `page init --package` replaces it.

- `page/` — the page's own browser-ready modules, styles, assets, `page/registry.json`
  and `page/widgets/`. These are candidate inputs only: each revision captures every
  file here but hidden ones (`revision_artifact.page_files`), and delivery reads the
  revision's captured copies.

- `media/` — content-addressed media shared across revisions (`media.py`). A name is
  always the one `media.media_name` mints for its bytes, and `page check` and the
  agent's message commands refuse any other name under `/media/`. Every host serves
  media at the page root, where documents, messages and the runtime address it.

- `events.jsonl` — the append-only event log, where an event's seq is its line number
  from 1. Stored rows keep the native session `context`, which application readers strip
  before admission, projection, delivery or output (`event_log.py`). The log also
  holds the acknowledgement cursor, the greatest `through` among its `receipt` events,
  so a cursor lives and ends with its log ([session-lifetime.md](session-lifetime.md)).

- `observations.jsonl` — a private, best-effort diagnostic trace: browser observations,
  server requests and thread-title requests, each `leaf` command's duration, and
  developer run context. It never enters page state or acknowledgement and is never
  served. `interaction_log.py` owns admission and reading, `browser/runtime/transport/interaction-log.js`
  what a tab sends and sheds, `interaction-batch.schema.json` a browser batch, and
  `leaf-dev logs response-times` the timing query over it.

- `user-views.json` — replaceable observations of the user's browser views, and when a
  document last showed the page (`user_views.py`). They are context for the author, not
  history, and page freshness and activation ignore them
  (`../../skills/leaf/references/conversation-loop.md`, "The user's view").

- `user-views.lock` — the lock serializing writes to `user-views.json`, which freshness
  and activation also ignore.

- `drafts.json` — the user's unsent message drafts, each draft's latest generation by
  its context (`drafts.py`), which every tab and device showing the page reads and
  writes. A tab hears it through its own store identity and version in `/api/news`,
  so no reading of the page, activation or watcher counts it, and the agent never
  reads it. It outlives the process serving it, as the log does. The identity is
  minted when the file is created, so it follows the file: a server restart keeps it,
  and a replaced file starts another store, whose versions say nothing of the first
  one's. Within one identity the version never goes back.

- `drafts.lock` — the lock serializing writes to `drafts.json`.

- `files.json` — local text-file grants written by `leaf file bind PAGE ID PATH`
  (`file_bindings.py`). The bound files remain their own authority, outside revisions
  and the log. A bound file may live in the page directory, as an example's
  `files/` does; its grant names it from there, so it moves with the directory.

- `data/` — one publication per source, `<source>.json`, which `leaf data set` writes
  and `leaf data clear` removes (`data.py`). The page holds a source exactly while its
  file exists.

- `stream.json` — what the harness observes of the claimant's task as it runs: its live
  activity, its draft reply and its reply reservations (`service.STREAM`). Readers load
  it through `service.read_stream`, and a missing file reads as an empty stream.
  [session-lifetime.md](session-lifetime.md) owns when each part stops being believed.

- `init.lock` — the lock that holds a re-initialization of the page, a `page init` or
  a renewal at this Leaf's page protocol, from the reading that decides it through the
  restart of the page's service, so a second one decides after the first
  (`vendoring._reinit`).

- `waiter.lock` — the bare-shell wait lease; a harness session uses
  `<state-home>/sessions/<session>.wait` instead
  ([session-lifetime.md](session-lifetime.md)).

- `preview.json` — the preview identity `leaf-dev preview` writes and the browser chrome
  labels (`service.PREVIEW`). Its presence exempts the page from the Stop hook's watcher
  guard.

- `service.json` — the desired server address, enabled state, lifetime, runtime
  provenance and current serving incarnation (`server_id`), plus a `restart` mark while
  `page init` holds a served page down to change its layer (`server.SERVICE`). `hosting.py`
  owns start, stop and revival, and [session-lifetime.md](session-lifetime.md#lifetime)
  the lifetime rule. The URL's access key is the machine's, not the page's
  (`server.host_key`).

- The page lock is the directory itself (`leases.page_locked`), so it writes nothing and
  ends with the page.

- `server.lock` — the serving incarnation's lease, whose bytes name the server's
  `server_id`. Only an exclusive kernel lock with the enabled service's identity proves
  that service live, and the file stays after release (`leases.py`).

- `<state-home>/claims/<page-key>.json` — the page's one canonical claim
  (`state.CLAIM`). `<state-home>/claims/<session-key>/<page-key>.json` is a symlink
  locating it for the owning session's discovery, which admits a locator only when the
  claim names that session, so a stale locator cannot take back a transferred page
  (`state.held_claims`, `state.retire_claim`). `page init` on a fresh page clears the
  prior claim and its locator.

- `<state-home>/http-connections/<page-key>.json` — the host's grants of authenticated
  HTTPS reads (`http_connections.CONNECTIONS`), each one origin, one credential header
  and a request allowance that `leaf connection bind` sets and every request, failed
  ones included, debits before network I/O. The 0600 record holds the credential value
  from the binding process's environment. Grants sit outside page resources, revisions
  and exports, so copying or publishing a page confers no access; samples and captured
  previews can't use them. The grant trusts every GET path on its origin, and the
  module header owns what a request may do.

- `<state-home>/rows/<page-key>.json` — disposable output of a serving page's own
  activity, for its neighbours (`server_rows.py`). No page's fold reads it.

- `<state-home>/render-readings/<page-key>.json` — the page's latest render check
  (`render_reading.py`), for its server (`handover_pass.py`), for the
  parts `leaf page state` lists and for the parts `leaf thread create --part` takes. No
  page's fold reads it, and without it a version is read again.

## Revision delivery

The live root serves the active revision, and revision and version addresses go through
the same delivery, all naming the page root as canonical (`revision_delivery.py`). The
revision manifest's `executable` digest decides whether an open tab patches its
document or replaces it (`revision_artifact.py`). The browser compares the two
authored DOM baselines to decide which widgets a patch keeps (`features/version.js`).

A publication that also changes the log stages its bundle, names it in its first
admitted event, and writes the revision marker last, and the next page transaction
finishes one that was interrupted (`revision_publication.py`).

## Page state

`leaf page state` is an on-demand reading of these files, which `agent_state.py`
assembles from the reading `/api/state` serves. It doesn't repeat the document: an
agent reads the HTML at `active.file` beside its `state`, which lists each user action
in force. `event_seq` is the last event the reading folded, which
`leaf page events --after` takes, and is not the acknowledgement cursor. Page ids and
event ids share one address space, so `page check` refuses an authored id shaped like
an event id.

Deliveries live outside page directories, at `<state-home>/deliveries/<id>.json`,
because one envelope can hold batches from several pages and must resolve the same in
every harness. Once written, a delivery never changes (`delivery.py`); Codex's mutable
delivery records are separate, and archiving them leaves the delivery
`leaf delivery read <id>` addresses in place.
