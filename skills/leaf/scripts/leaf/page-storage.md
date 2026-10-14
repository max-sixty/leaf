# Page storage

## Files

The author writes `index.html` and `page/` candidate inputs. Leaf owns the
other page files and the external state listed below.

- `index.html` — mutable author document. The server validates it before activation and
  never serves it directly. An invalid save creates no revision, leaves the previous
  valid revision live, and exposes the diagnostic in page state and browser chrome.

- `revisions/rN-H.html` — immutable valid-save marker; N is activation order and H is
  the first 16 hex characters of the artifact-manifest digest. Its sibling
  revisions/rN-H/ captures index.html, manifest.json, registry, and every dependency
  needed to deliver that revision. The complete bundle is durable before the marker
  appears. Identical artifacts reuse a revision; changed inputs create one. A bundle
  hard-links each resource whose bytes the previous revision captured, so its files
  share inodes and are never written in place. See
  “Revision delivery” below for document replacement and widget retention.

- `/versions/v1.html…` — virtual public addresses. Each `note` event maps a version to
  its immutable revision, and the server renders that revision at the stable version
  URL. No second HTML copy is stored in the durable page record. A static-site build may
  materialize the same responses beside a copied record as disposable delivery output;
  those files are never an authority. A pinned version therefore never moves while later
  source saves become live.

- `leaf.js` — the browser entry, served at /leaf.js

- `theme.css` — tokens, element styles, class idioms, element-widget CSS

- `shadow.css` — the rules declared shadow trees also need; theme.css carries them too,
  ahead of each package's own rules

- `registry.json` — effective widget schemas and layer metadata. Composition and
  identity are defined in [layer-registry.md](layer-registry.md).

- `instructions/` — shared package instructions grouped by audience. Files with the
  same name concatenate in package order, each under a heading naming its package.
  `page instructions` composes them with selected registry instructions
  (`../../references/packages.md`, "Package contract").

- `icon.svg` — tab icon; its lf-tone element follows the banner's status colour

- `runtime/` — private browser owners plus the public widget-api.js module

- `widgets/` — one ES module per upgraded widget (lf-tabs.js, lf-board.js)

- `vendor/` — vendored third-party assets (sortable.esm.js, plot.esm.js), and whatever a
  selected package brings (mermaid.esm.js)

- `page/` — mutable page-specific browser-ready modules, styles, assets,
  page/registry.json declarations, and page/widgets/ modules. These are candidate inputs
  only; delivery reads their captured revision copies, never these mutable files
  directly.

- `media/` — content-addressed page media, shared across revisions. `media.py` owns
  ingestion through `page media` and `/api/media`. Browser drafts and messages refer to
  them with Markdown; a public filename always identifies the same bytes. That name is
  `schema.MEDIA_DIGEST`'s, the one `media.media_name` mints and the server serves;
  `page check` and the agent's message doors refuse any other name under `/media/`,
  and the browser and the Worker read a reference by its directory alone. A revision
  captures the media its document names, but every host serves media at the page root,
  and documents, messages, and the runtime all address it there.

- `events.jsonl` — append-only event log; an event's seq is its line number (1-based)

- `observations.jsonl` — private, best-effort diagnostic JSON-lines trace of
  server requests, browser observations and developer run context. It never enters
  page state or acknowledgement and is never served as an asset. The semantic
  `events.jsonl` remains the durable record of accepted decisions.

  Every stored row has a host-clock `ts`. Browser observations retain their wall
  clock as `observed_at`, a positive `sequence`, finite nonnegative `monotonic_ms`,
  and `visibility` (`visible` or `hidden`). Admission validates these common fields
  once; observation types and other payload fields remain open. `/api/interaction`
  adds session identity and the scoped root-relative page address. Descendant sample
  activity stays in the containing page's trace after a sample is released.
  Server request rows have type `request`, method, path without query, status and
  duration; successful news looks and resource-byte delivery are excluded.

  `leaf page interactions` orders by host time and keeps the first copy of each
  `(session, sequence)`. Its end cutoff defines observed history, then gap detection
  precedes start, session and type filtering. Missing sequences remain visible under
  a type filter; an unsent tail leaves no evidence. Server and developer records have
  no browser session association. A torn append line is skipped. Human output uses
  local time and shortens values; `--json` preserves admitted payloads.

  Each browser sequence names one observation. A serialized observation over 40,000
  UTF-8 bytes becomes `interaction_omitted`, retaining its original type, size and
  common timing fields instead of its payload. There is no multipart transport or
  reassembly. A tab retains at most 512 pending observations, shedding resource
  timings and repeated input first, then older actions to admit new actions. New
  repeated observations yield to pending actions. Failed batches retry; page hide
  may resend an in-flight batch. Sequence gaps expose lost observations.

  Command observations capture the selected title and description, focus and scroll
  before execution. `event_submit` records local enqueue with its `attempt`;
  `reply_visible` records actual message or working words entering a visible banner,
  thread, or On list, with reply/input identity and presentation kind. Generic
  delivery labels do not count. Compare monotonic values only within one browser
  session; host receipt and browser wall time do not measure send-to-visible latency.
  Developer `run_context` declares `purpose`, `run` and optional authored source or
  test identity before synthetic input or preview use. Purpose describes a run,
  rather than proving a human gesture. `leaf-dev response-times` preserves missing
  evidence and exports timing rows without message text.

- `user-views.json` — replaceable per-document browser
  observations (`user_views.py`). These are author
  context, not event history or source inputs. They are excluded from page freshness
  and activation. `../../references/conversation-loop.md`, "The user's view", defines
  the agent reading.

- `user-views.lock` — the independent lock serializing observation writes;
  excluded from page freshness and activation.

- `data.json` — the current contract each external-data source id was set under.
  `data.py` owns storage and updates.

- `files.json` — explicit local text-file grants, written by `leaf file bind PAGE
  ID PATH` as `{ "bindings": { "ID": "/absolute/canonical/path" } }`.
  `file_bindings.py` owns the grants and current-file reads and writes. Browser
  requests name only a binding, never a path. The page's reading stamps each bound
  file and the state answer carries those stamps under `files`, so a tab hears a
  write from outside Leaf without reading the file on a timer. These files remain their own authority:
  editing is mechanical browser state, outside document revisions and event history.
  The API reads current UTF-8 text up to 256 KiB and saves against a revision of its
  path and exact bytes, preserving LF or CRLF and file permission bits. Mixed line endings,
  binary controls, and later symlink substitutions are refused. Captured previews
  cannot read or save live files; immutable views offer no editor access. Target locks
  under `<state-home>/files/` serialize file-editor saves, including different pages
  bound to the same path. An unrelated
  writer which does not use those locks can still race the last comparison and atomic
  replacement; this is not an operating-system compare-and-swap guarantee.

- `data/` — one JSON publication per source, `<source>.json`, holding `run`,
  `updated`, and `value` together. `leaf data set` validates and atomically writes
  it; a new write gets a new opaque run receipt, including an identical value.
  Copying the page preserves that receipt. Readings trust the publication's shape
  and validate its value against the recorded contract. Deferred record fields served by
  `/api/deferred` come from the value in these same publications.

- `status.json` — the agent's `waiting` or `idle` declaration, observed activity,
  and reply reservations. The work in hand is no status: it is the log's `start` events.
  [session-lifetime.md](session-lifetime.md) owns their writers and lifetimes;
  the `delivery` header defines reply reservations, and `thread.py` reserves and
  releases them. Every reader loads it
  through `service.read_status`, which reads a missing file as no declaration.

- `waiter.lock` — stable bare-shell wait lease file; harness sessions instead
  use `<state-home>/sessions/<session>.wait`. See [session-lifetime.md](session-lifetime.md).

- `viewed.json` — last visible browser attention, written by the server and absent until
  first viewed. `presence.py` owns throttled renewal, which the server runs as a
  visible tab asks for news; hidden tabs do not renew it.

- `cursor.json` — durable acknowledged position in this page's event log, retained
  with that log when its serving process is replaced. Acknowledgement and
  log replacement rules are defined in [session-lifetime.md](session-lifetime.md).

- `preview.json` — the preview identity browser chrome labels, written by
  `leaf-dev preview`, which decides what a preview tells the browser: the server
  hands the file to the page whole. Its presence exempts the page from the handoff's watcher guard.

- `service.json` — desired server address, enabled state, lifetime, and runtime
  provenance and current serving incarnation (`server_id`), plus a `restart` mark while `page init` holds a served page down to
  re-vendor it, which any other stop replaces so the restart leaves that stop
  alone. `hosting.py` owns start/stop, restart, and revival;
  [session-lifetime.md, “Lifetime”](session-lifetime.md#lifetime) owns the lifetime rule.
  The URL's access key belongs to the machine's state home.

- The page lock is the directory itself: `leases.page_locked` flocks a descriptor on
  it to serialize service changes, re-vendoring, and contract-bearing writes, so it
  writes nothing and ends with the page.

- `server.lock` — process-held serving incarnation lease. Its bytes name the
  HTTP server's `server_id`; only an exclusive kernel lock with the same identity
  as the enabled service proves that service is live. Preparation clears retained
  metadata under a shared lock before taking the exclusive lease, so a private
  listener cannot advertise a prior incarnation. `hosting.py` waits for release
  on stop, after sockets close. The stable file remains after release.

- `<state-home>/claims/<page-key>.json` — the page's one atomic canonical claim
  payload. `<state-home>/claims/<session-key>/<page-key>.json` is a symlink
  locating that payload for the owning session's discovery. The locator is prepared
  before ownership commits in the payload; failed preparation leaves ownership
  intact. Discovery admits a locator only when the payload names that partition's
  session, so a stale locator cannot reclaim a transferred page. Named watches
  follow prepared locators' canonical targets until ownership commits.
  Named discovery reads only that session's partition; global observation reads
  the canonical payloads directly. Atomic updates by existing
  page-server writers retain the payload's path and leave discovery intact.
  Scans ignore claims for missing pages; fresh page initialization clears
  the prior claim under the page lock. [session-lifetime.md](session-lifetime.md) owns
  claimant identity, harness, and lifetime.

- `<state-home>/rows/<page-key>.json` — disposable delivery output of a serving
  page's own canonical activity. `server_rows.py` owns the record, producer and
  freshness contract. It is never read by a page's semantic fold; losing it only
  hides that neighbor until the server's next maintenance look.

## Revision delivery

The live root serves the active revision, and revision and version addresses go
through the same delivery; all three name the page root as canonical. The revision
manifest's executable and widget digests decide whether an open tab replaces its
document or keeps its widgets (`revision_artifact.py`).

## Page state

`leaf page state` is an on-demand reading of these authorities. Its
`layer` object, shared with `/api/state`, reports the vendored generation,
fingerprint, server identity, packages, and producer;
`source` names `index.html`, whether that candidate is live, and any validation
error, including the refusal of a layer this Leaf cannot serve
(`layer.incompatible_layer`). `active.file` names the immutable revision the live
root actually shows when one exists; `data` names the contract file, the value directory, and any source whose
value fails its contract.
`active.executable`, shared with `/api/state`, gives the active revision's
nullable executable digest. Delivery emits `<meta name="lf-executable">` when a
digest is available; `../../assets/runtime/version.js` owns the resulting install choice.
`event_seq` is the last event folded into the snapshot and can be passed to
`leaf page events --after`; it is distinct from the acknowledgement cursor.

The page's document is not repeated in the reading: an agent reads the HTML at
`active.file` beside `state`, which lists each user action in force by widget, unit and
verb with the detail it carries, so where the two differ the page shows the action.
`data_bindings` names each bound source and the widgets that read it, and
`data/<source>.json` holds its publication.

`leaf page state <page> <id>` narrows the reading to what `<id>` names. A message,
or a widget frozen into one, names its thread: the reading is that thread's current
messages, with bounded history selected by `--after` and `--limit`, and each
message's frozen markup under
`content` (`construction.py`), since that markup has no file of its own. An authored
node keeps its `tag`, effective `attrs` and `content`, and `source` line and column; a
event in force supplies its exact `state` and origin, and `authored` preserves the
input it replaced. Widget `inputs` join each binding to its source's current value,
contract, source id and revision, or to the `error` a failing value reads as;
contracts with a deferred record field expose the manifest plus the value file and
its revision for their payload. The reading's `content_source` names the thread and
vocabulary file. A widget on the page names itself: the reading is its `widget`
element, the `state` and `reports` in force on it, the open `todos` on it,
the canonical `asks` sourced by it, and the `workflows` it is the subject of, with
their `activity` obligations. Page ids
and event ids share one address space, which is why `page check` refuses an authored
id shaped like an event id. Default `page state` thread entries stay compact. Raw
diagnostic history belongs to `leaf page events`, and the page's `registry.json` owns
the vocabulary.

Immutable deliveries live outside page directories at
`<state-home>/deliveries/<id>.json`, because one envelope can contain complete
batches from several pages and must resolve identically in every harness. Once
written, the file's `format` (`delivery.DELIVERY_FORMAT`), id, capture time,
acknowledgement and batches never change. Delivery
records are separate mutable transport state; acknowledgement can archive
those records without moving or rewriting the delivery addressed by `leaf
delivery read <id>`.

A publication with dependent log transitions stages its immutable bundle before
admitting its prerequisite. A `publication` coordinate on the note, replacement
reply, or first automatic reanchor names that exact bundle. The HTML marker
appears only after every required transition is durable. Entering a page
transaction completes any journaled publication whose marker is missing, using
the staged inputs and prior immutable revision. A staged bundle with no admitted
prerequisite is absent; a later mutable source edit never substitutes for the
journaled input (`revisioning.finish_publications`).
