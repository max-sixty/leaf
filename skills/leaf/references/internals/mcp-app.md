# MCP App transport

Status: experimental. The Codex plugin registers this transport so the complete
Leaf interface can be evaluated in shipped MCP Apps hosts without replacing the
browser fallback.

## Authorities

The bundled stdio server is a delivery route over the existing page model.
`index.html` starts state, immutable revisions hold valid saves,
`comments.jsonl` changes them, and `PageTransaction` remains the read/write
boundary. The MCP resource, its iframe shell, and its loopback server own no
current state, replay, undo, versions, or delivery cursor. Closing an app loses
only that presentation.

The Codex manifest launches `bin/leaf mcp` from the installed plugin root. The
server advertises `text/html;profile=mcp-app` and two resources:

- `ui://leaf/page/v1.html` is the primary complete page;
- `ui://leaf/review/v1.html` is an explicit comments-only snapshot fallback.

## Complete page

`leaf_present` is model-visible and binds the complete resource. `leaf_refresh`
is app-only. Both activate and read the named initialized page using
`PageStateService`; presentation can therefore create a valid immutable revision
and does not advertise the read-only hint. The ordinary text and structured
result carry a small summary. The local frame address and optional ordinary
browser URL live only under `_meta.leaf`, which the host sends to the app without
adding it to model context.

One `ProcessPageServer` binds `127.0.0.1` on an ephemeral port before the resource
is registered. Its exact `http://localhost:<port>` origin is the resource's sole
`frameDomains` entry. Every opened page receives an unguessable
`/p/<capability>/` path on that origin; the process reuses a page's path, writes
no `service.json`, and drops every path when it exits. There is no wildcard CSP,
query token, cookie, or durable host key in the tool result.

The canonical page contract speaks root-relative Leaf routes. At this multiplexing
boundary, every HTML response and validated frozen `markup` value in state passes
through document route scoping, textual served assets scope their known routes, and
version URLs in state receive the page prefix. Together these adapt `api`, `runtime`,
`widgets`, `vendor`, `media`, registry, theme, icon, and runtime paths below the
capability. This keeps arbitrary package modules on the ordinary
`/runtime/widget-api.js` contract while ensuring every subsequent request proves the
same page capability. Unknown or unscoped paths receive 404. The nested frame
therefore runs the same authored document, package modules, comments, actions,
versions, state stream, and `EventEndpoint` as an ordinary Leaf tab.

This route is local-host-only. The browser rendering the MCP App must share the
machine running the stdio server. A remote page address requires an explicit
deployment and security contract rather than a widened loopback server.

## Snapshot fallback

`leaf_present_snapshot` is a separate model-visible fallback, not the primary
interface and not a compact vocabulary projector. It renders inert authored
markup and theme rules, supports page, element, and passage comments, and offers
the ordinary browser route when one exists. `leaf_snapshot_apply_event` and
`leaf_snapshot_refresh` are app-only. The append gate canonicalizes abbreviated
text anchors before storing them, so fallback clients do not create weaker
durable anchors. Served runtime anchors keep the browser reading that already
resolved them; only the snapshot endpoint requests file-side capture.

The app reads a passage and resolves nothing. Its quote comes from the rendered
document's own text nodes, with one space wherever the enclosing text block
changes; the tag vocabulary for that arrives in the tool result as `textBlocks`,
so the app keeps no list of its own. A selection's `toString()` gives back the
host's paint instead of the page's words — the theme uppercases a table header
and an eyebrow, and a `<br>` breaks a run the version holds unbroken — and an
anchor written from it names a passage no reading of the file can find. An
element anchor names an element of the page, and the app's own shell stands on
the same composed path wearing ids that belong to no version. Everything after
that is the gate's. It writes the neighbours that tell two copies apart, and
refuses a quote repeated without unique context rather than reading document
order as identity. The app shows that refusal with the reader's draft still in
the box.

The resource is self-contained, runs no authored code, and declares no network
domains. It does not implement package actions. The old single-choice
`lf-options` projector is deliberately absent: a fixed shape was a second Leaf
interface and understated what the complete route can carry.

## Return and wake

Both surfaces persist reader gestures before reporting success. Neither calls
`ui/message` to claim delivery or advances the event cursor from an MCP response:
the host may accept that JSON-RPC request without starting or durably queueing a
turn. `leaf codex start <page>` remains the authoritative return carrier. Its
detached adapter waits on the same log, queues an exact persisted batch into the
same Codex task, and acknowledges only after durable queue acceptance.

The complete-page resource is a tracked bundle generated from `scripts/mcp-app/`
by `scripts/vendor.py mcp-app`; do not patch the generated HTML under
`assets/vendor/` directly. The snapshot resource is authored by hand as one
self-contained asset, `assets/mcp-app.html`.
