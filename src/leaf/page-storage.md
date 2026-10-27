# Page storage

## Files

The author writes `index.html` and the `page/` candidate inputs. Leaf owns every other
file below, in the page directory or the state home. Each entry names the module that
owns it, whose header holds the rest of its contract.

Each JSON record below is a `state.Record`, declared once beside its owning module,
whose functions are its only writers. A record carries the protocol at which its kind's
shape last changed, and one this Leaf does not read reads as absent. A state-home
record whose pages are gone is removed whichever Leaf wrote it (`state.retire_if_gone`).

- `index.html` — the author's mutable document. The server validates it before
  activation and never serves it directly. An invalid save creates no revision, leaves
  the previous revision live, and shows its diagnostic in page state and the browser.

- `revisions/rN-H.html` — the marker of one valid save, where N is the activation order
  and H the first 16 hex characters of the artifact manifest's digest. Its sibling
  `revisions/rN-H/` holds everything needed to deliver that revision but the browser
  runtime, which the serving Leaf supplies (`runtime_selection.py`), durable before
  the marker appears. Identical artifacts reuse a revision, and a bundle hard-links the
  resources whose bytes the previous revision captured, so no file is written in place
  (`revision_artifact.py`).

- `/versions/v1.html…` — virtual addresses. Each `note` event maps a version to its
  immutable revision, which the server renders at the version's URL, so a pinned
  version never moves as later saves go live. A static-site build may write these
  responses out as disposable delivery output, never an authority.

- `theme.css` — tokens, element styles, class idioms and element-widget CSS.

- `shadow.css` — the rules declared shadow trees also need; `theme.css` carries them
  too, ahead of each package's own rules.

- `registry.json` — the effective widget schemas and layer metadata
  ([layer-registry.md](layer-registry.md)).

- `instructions/` — package instructions by audience, which `page instructions`
  composes (`layer.composed_instructions`; `../../skills/leaf/references/packages.md`,
  "Package contract").

- `icon.svg` — the tab icon, whose `lf-tone` element follows the page's status colour.

- `runtime/` — the browser modules a selected package adds beside the runtime's own.

- `widgets/` — one ES module per upgraded widget.

- `vendor/` — the third-party assets packages bring, beside the runtime's own.

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
  served. `interaction_log.py` owns admission and reading, `browser/runtime/interaction-log.js`
  what a tab sends and sheds, `interaction-batch.schema.json` a browser batch, and
  `leaf-dev response-times` the timing query over it.

- `user-views.json` — replaceable observations of the user's browser views, and when a
  document last showed the page (`user_views.py`). They are context for the author, not
  history, and page freshness and activation ignore them
  (`../../skills/leaf/references/conversation-loop.md`, "The user's view").

- `user-views.lock` — the lock serializing writes to `user-views.json`, which freshness
  and activation also ignore.

- `files.json` — local text-file grants written by `leaf file bind PAGE ID PATH`
  (`file_bindings.py`). The bound files remain their own authority, outside revisions
  and the log.

- `data/` — one publication per source, `<source>.json`, which `leaf data set` writes
  and `leaf data clear` removes (`data.py`). The page holds a source exactly while its
  file exists.

- `stream.json` — what the harness observes of the claimant's task as it runs: its live
  activity, its draft reply and its reply reservations (`service.STREAM`). Readers load
  it through `service.read_stream`, and a missing file reads as an empty stream.
  [session-lifetime.md](session-lifetime.md) owns when each part stops being believed.

- `waiter.lock` — the bare-shell wait lease; a harness session uses
  `<state-home>/sessions/<session>.wait` instead
  ([session-lifetime.md](session-lifetime.md)).

- `preview.json` — the preview identity `leaf-dev preview` writes and the browser chrome
  labels (`server.PREVIEW`). Its presence exempts the page from the Stop hook's watcher
  guard.

- `service.json` — the desired server address, enabled state, lifetime, runtime
  provenance and current serving incarnation (`server_id`), plus a `restart` mark while
  `page init` holds a served page down to re-vendor it (`server.SERVICE`). `hosting.py`
  owns start, stop and revival, and [session-lifetime.md](session-lifetime.md#lifetime)
  the lifetime rule. The URL's access key is the machine's, not the page's
  (`server.host_key`).

- The page lock is the directory itself (`leases.page_locked`), so it writes nothing and
  ends with the page.

- `server.lock` — the serving incarnation's lease, whose bytes name the server's
  `server_id`. Only an exclusive kernel lock with the enabled service's identity proves
  that service live, and the file stays after release (`leases.py`).

- `<state-home>/claims/<page-key>.json` — the page's one canonical claim
  (`service.CLAIM`). `<state-home>/claims/<session-key>/<page-key>.json` is a symlink
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

## Revision delivery

The live root serves the active revision, and revision and version addresses go through
the same delivery, all naming the page root as canonical (`revision_delivery.py`). The
revision manifest's `executable` digest decides whether an open tab patches its
document or replaces it, and its `widgets` digests decide which widgets a patch keeps
(`revision_artifact.py`).

A publication that also changes the log stages its bundle, names it in its first
admitted event, and writes the revision marker last, and the next page transaction
finishes one that was interrupted (`revisioning.py`).

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
