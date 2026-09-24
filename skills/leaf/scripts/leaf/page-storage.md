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
  appears. Identical artifacts reuse a revision; changed inputs create one. See
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

- `guidance/` — package-owned guidance grouped by audience. Files with the same name
  concatenate in package order, each under a heading naming its package;
  `page guidance` reads any audience

- `icon.svg` — tab icon; its lf-tone element follows the banner's status colour

- `runtime/` — private browser owners plus the public widget-api.js module

- `widgets/` — one ES module per upgraded widget (lf-tabs.js, lf-board.js)

- `vendor/` — vendored third-party assets (sortable.esm.js, plot.esm.js), and whatever a
  selected package brings (agentic-mermaid.esm.js)

- `page/` — mutable page-specific browser-ready modules, styles, assets,
  page/registry.json declarations, and page/widgets/ modules. These are candidate inputs
  only; delivery reads their captured revision copies, never these mutable files
  directly.

- `media/` — content-addressed page images, shared across revisions. `media.py` owns
  ingestion through `page media` and `/api/media`. Browser drafts and messages refer to
  them with Markdown; a public filename always identifies the same bytes.

- `events.jsonl` — append-only event log; an event's seq is its line number (1-based)

- `data.json` — the contract each external-data source id was first set under.
  `data.py` owns storage and updates.

- `data/` — one JSON file per source, `<source>.json`, holding its current value.
  Any process may rewrite one; readings validate it against the recorded contract.
  Deferred record fields served by `/api/deferred` come from these same files.

- `status.json` — work declarations and transient delivery handling, observed activity,
  and reply bindings. [session-lifetime.md](session-lifetime.md) owns their writers and
  lifetimes; `conversation.py` owns response reservations and their release.

- `waiter.lock` — bare-shell wait lease; host sessions instead use
  `<state-home>/sessions/<id>.wait`. See [session-lifetime.md](session-lifetime.md).

- `viewed.json` — last visible browser attention, written by the server and absent until
  first viewed. `http.py` owns throttled renewal; hidden tabs do not renew it.

- `cursor.json` — acknowledged position in this page's event log. Acknowledgement and
  log replacement rules are defined in [session-lifetime.md](session-lifetime.md).

- `preview.json` — the preview identity browser chrome labels, written by
  `scripts/preview.py`, which decides what a preview tells the browser: the server
  hands the file to the page whole. Its presence exempts the page from the handoff's watcher guard.

- `service.json` — desired server address, enabled state, lifetime, and runtime
  provenance. `hosting.py` owns start/stop and revival;
  [session-lifetime.md, “Lifetime”](session-lifetime.md#lifetime) owns the lifetime rule.
  The URL's access key belongs to the machine's state home.

- `server.lock` — process-held server lease. `hosting.py` waits for its release on stop,
  after the server has closed its sockets.

- `<state-home>/claims/` — one atomic claim per resolved page, independent of its page
  directory. [session-lifetime.md](session-lifetime.md) owns claimant identity,
  release, harness, and lifetime.

Every record the state home keeps about a page — its claim, its transition and
preview locks under `page-locks/`, a delivery naming it — outlives the directory,
which is usually deleted from outside leaf. `sweep.py` owns the one rule that
removes such a record once its page is gone.

## Revision delivery

The live root follows the active revision. Immutable revision and version
addresses use the same delivery boundary, and all three advertise the page
root as their canonical URL. The executable and widget digests in the revision
manifest control document replacement and widget retention;
`revision_artifact.py` owns their inputs and construction.

## Page state

`leaf page state` is an on-demand reading of these authorities. Its
`layer` object, shared with `/api/state`, reports the vendored generation,
fingerprint, kernel runtime identity, packages, and producer;
`source` names `index.html`, whether that candidate is live, and any validation
error. `active.file` names the immutable revision the live root actually
shows when one exists; `data` names the contract file, the value directory, and any source whose
value fails its contract.
`active.executable`, shared with `/api/state`, gives the active revision's
nullable executable digest. Delivery emits `<meta name="lf-executable">` when a
digest is available; `../../assets/runtime/version.js` owns the resulting install choice.
`event_seq` is the last event folded into the snapshot and can be passed to
`leaf events --after`; it is distinct from the acknowledgement cursor.

`content` joins the authored tree with standing state and declared data inputs.
It includes ordinary HTML and content in disclosures or inactive tabs. An authored node
keeps its `tag`, effective `attrs` and `content`, and `source` line and column.
`content_source` supplies their shared immutable `file`, `revision`, mutable
`edit_file`, `matches_active`, and vocabulary-file path. A node's `vocabulary`
is its tag key in that file. A standing event supplies its exact `state` and origin;
`authored` preserves the input it replaced. An opaque widget exposes its authored
source and vocabulary entry rather than claiming to reproduce its rendered text.

Each node's `edit` identifies its mutation owner. A source edit carries its stable
id when present and `matches_active`; the target file is inherited from
`content_source.edit_file`. Source locations apply to that mutable file only when
it matches the active revision. Generated children name their originating event and
the widget in which their markup can be authored. `leaf conversation read <page> <id>`
reads one conversation's current messages and frozen markup under `content`, with
bounded history selected by `--after` and `--limit`. Its `content_source` names the
conversation and vocabulary file; message identities locate the frozen source. Default
`page state` conversation entries stay compact.

Widget `inputs` join each binding to its source's current value, contract, source
id, and revision, or to the `error` a failing value reads as. Each input's `edit`
names the value file to rewrite. Contracts with a deferred record field expose the
manifest plus that file and its revision for their payload. The compact
`elements`, `state`, and lifecycle indexes remain available for machine queries.
Raw diagnostic history belongs to `leaf events --conversation`, and the page's
`registry.json` owns the vocabulary.

Immutable deliveries live outside page directories at
`<state-home>/deliveries/<id>.json`, because one envelope can contain complete
batches from several pages and must resolve identically in every host. The file's
`leaf-delivery-v3` format, id, capture time, carrier, acknowledgement, and
batches never change. Delivery
records are separate mutable transport state; acknowledgement can archive
those records without moving or rewriting the delivery addressed by `leaf
delivery read <id>`.
