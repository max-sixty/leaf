# Page storage

A page directory holds:
    index.html            mutable author source. The agent writes only this file.
                         The server validates it before activation and never serves
                         it directly. An invalid save creates no revision, leaves the
                         previous valid revision live, and exposes the diagnostic in
                         page state and browser chrome.
    revisions/rN-H.html… immutable valid saves, where N is activation order and H is
                         the first 16 hexadecimal characters of the source digest.
                         A changed valid source becomes the next revision; identical
                         bytes reuse the existing one. The live root follows the
                         active revision.
    /versions/v1.html…   virtual public addresses. Each `note` event maps a version to
                         its immutable revision, and the server renders that revision
                         at the stable version URL. No second HTML copy is stored.
                         A pinned version therefore never moves while later source saves
                         become live.
    leaf.js              the browser entry, served at /leaf.js
    theme.css            tokens, element styles, class idioms, element-widget CSS
    registry.json        the widget vocabulary: JSON Schema per lf-* tag, plus the
                         layer-wide facts under $ — $idioms, $languages, $keys (what
                         each x- key means), and the page's vocabulary stamp ($events,
                         x-state): the one statement of what this page's vendored
                         runtime speaks. $layer keeps the reload-safety generation,
                         stable content fingerprint, selected packages, and optional
                         producer commit/dirty provenance
    guidance/            package-owned guidance grouped by audience. Files with the
                         same name concatenate in package order; `page guidance` reads
                         any audience
    icon.svg             the mark the tab wears, whose lf-tone element the runtime
                         paints in whatever colour the banner's dot is wearing — so a
                         reader with six leaves open sees which one wants them
                         without opening any
    runtime/             private browser owners plus the public widget-api.js module
    widgets/             one ES module per upgraded widget (lf-tabs.js, lf-board.js)
    vendor/              vendored third-party assets (sortable.esm.js, plot.esm.js),
                         and whatever a selected package brings (beautiful-mermaid.esm.js)
    media/               images the page shows, each named by the hash of its bytes
                         (`page media`). Not vendored — this is the page's content,
                         not the layer's — but served the same way.
                         Content-addressing is what lets content live here at all:
                         a name means one set of bytes forever, so a revision the
                         user approved cannot show them different pixels later,
                         and two versions showing the same screenshot share one
                         file rather than carrying a copy each. It is also the
                         only door an image has into a page: the page's author is
                         a language model, and a screenshot is a megabyte of
                         base64 it cannot type — nor should each version carry a
                         copy that `version check` walks and a browser reloads.
                         So the transport was never an optimisation over
                         inlining; inlining was never available
    events.jsonl         append-only event log; an event's seq is its line number (1-based)
    data.json            explicit authority for page-bound sources: each record keeps
                         its contract identity, may have a replaceable current value
                         with the data revision that wrote it and the revision ids of
                         earlier values without retaining those values,
                         and may retain immutable captures selected by document
                         versions or frozen threads. Initialized as the empty revision
                         0 store. Agent page state names this file and its revision,
                         joining selected values to their bound widget inputs.
                         Browser state normally carries the
                         validated values; for a contract-declared fragment field it
                         carries only the surrounding manifest, and `/api/data` reads
                         one keyed payload from this same revision on demand. No split
                         payload becomes a second authority.
    status.json          the agent's declared state: {"state": working|waiting|idle, "detail", "ts"};
                         detail is the finer grain the banner reads out after the
                         state — what the agent is doing while working, what it
                         needs from the reader while waiting;
                         "work" holds typed, sequence-bounded claims on comment
                         threads or page widgets. At the state boundary these
                         private records become canonical claim updates, which
                         their local receipts show beside the page-wide banner
                         (`leaf status … --on`). Delivery pickup never writes
                         this file; it is a page-owned event in events.jsonl
    waiter.lock          bare-shell `leaf wait` lease, held open and locked for
                         the command's life. A host session holds one lease at
                         sessions/<id>.wait instead, because one wait watches all
                         of that session's pages
    viewed.json          when a browser last held the page open, bumped
                         (throttled) by the server while a tab's news stream
                         stands; absent for a page nobody has ever opened, which
                         would otherwise be indistinguishable from one the user
                         studied and left
    cursor.json          seq of the last user event acknowledged after the complete
                         batch reached its next durable consumer — written by
                         `leaf ack`; a page-owned pickup event separately names
                         the exact reader events accepted by that consumer
    preview.json         optional safe metadata written only by the repository's live
                         example preview: example, checkout name, interaction
                         (`reader` or `automation`), start time, and optional commit/
                         dirty state. The server projects these named fields into
                         preview-only browser chrome; it never serves this file or an
                         absolute checkout path. Its presence is the one statement
                         "this page is a preview, not a handoff", so the loop guard
                         also reads it and asks no watcher of the page
    service.json         {"host", "bind", "port", "enabled", "lifetime", "runtime"}:
                         the durable desired service. It preserves the exact URL an
                         open browser holds and whether a session may end it.
                         A crash leaves it enabled so `leaf wait` can revive it;
                         `server stop` disables it and leaves the address and
                         lifetime ready for a later start. `runtime` identifies the
                         payload path and its available Git provenance. The key in the
                         URL is the machine's, not the page's, and lives in the state home
    server.lock          a contentless live-server lease, locked for the process's
                         whole life. The kernel releases it on a crash. A stop
                         asks the server to exit through service.json and waits
                         for this lease, so no listening or accepted socket
                         remains when the command returns
    claims/              outside the page, one atomic record per resolved page:
                         its last claimant, release time, and the lifetime it
                         rests on.
                         Keeping provenance outside the disposable page lets
                         ownership discovery survive a page moving between sessions

`leaf page state` is an on-demand reading of these authorities. Its
`layer` object, shared with `/api/state`, reports the vendored generation,
fingerprint, packages, and producer;
`source` names `index.html`, whether that candidate is live, and any validation
error. `active.file` names the immutable revision the live root actually
shows when one exists; `data.file` always names a readable JSON store. `event_seq`
is the last event folded into the snapshot and can be passed to `leaf events
--after`; it is distinct from the acknowledgement cursor.

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
it matches the active revision. Reconcile a rejected candidate by id and content
before editing. Generated children name their originating event and the widget in
which their markup can be authored. `leaf page state <page> --thread <id>` selects
one thread's current messages and frozen markup under `content`. Its
`content_source` names the conversation, thread, and vocabulary file; message
identities locate the frozen source. Edits continue that conversation instead of
rewriting events or restating page state. Default thread entries stay compact.

Widget `inputs` join each binding to its selected value or captured snapshot,
contract, source id, data revision, and mutation route. Fragmented contracts expose
the manifest plus the exact `data.json` file, path, and revision for their payload.
Live inputs declare `edit.operation: "data set"`; pinned inputs declare
`"capture-and-rebind"`, since the source update alone leaves the selected capture
unchanged. A pinned input in frozen markup declares `"capture-and-reply"` and its
thread: a new message presents the replacement capture. The compact `elements`, `state`,
and lifecycle indexes remain available for machine queries. Exact thread history
belongs to `leaf events --thread`, and the page's `registry.json` owns the vocabulary.
