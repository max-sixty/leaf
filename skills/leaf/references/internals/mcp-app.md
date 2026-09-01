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
server advertises `text/html;profile=mcp-app` and one adaptive resource,
`ui://leaf/page/v1.html`. Every presentation and app-only tool binds that same
URI. Hosts may therefore reuse one server-level app resource without applying a
snapshot renderer to a complete-page result or the reverse.

The resource selects its behavior from an explicit private payload contract:
`leaf.page/v1` with `mode: page`, or `leaf.snapshot/v1` with `mode: snapshot`.
Its CSP is the superset required by those two modes: no connect or resource
domains, and the exact process page origin as its sole frame domain. Snapshot
mode does not use that frame capability.

Both presentation tools return readable tool refusals for an uninitialized
page, a page with no active revision, and a missing, malformed, or stale vendored
registry. Layer failures name `leaf page init`; they do not surface as server
faults.

## Complete page

`leaf_present` is model-visible and `leaf_refresh` is app-only. Both are marked
read-only: they read the durable page, while the process-local HTTP origin is
ephemeral presentation transport. The ordinary text and structured result carry
a small summary. The local frame address and optional ordinary browser URL live
only under `_meta.leaf`, which the host sends to the app without adding it to
model context.

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

The app first reads the host-approved `sandbox.csp.frameDomains` capability. When
that field is present and lacks the exact inline origin, it never assigns the
iframe URL and immediately calls the read-only `leaf_snapshot_refresh`. An absent
field is unknown rather than refusal; an exact match is permission to try.

For those attempted frames, the app does not treat `load` as success because
browsers fire it for network and policy error documents too. The routed server
adds one transport-only module that posts a minimal readiness marker after the
canonical runtime sets `data-lf-presented`. The app accepts that marker only from
its exact frame window and origin, and reveals the frame only then. If no marker
arrives within the bounded wait, it calls the same snapshot refresh and renders
that result. Both fallback paths retain the full page's browser or inline URL for
the Full page action.

This route is local-host-only. The browser rendering the MCP App must share the
machine running the stdio server. A remote page address requires an explicit
deployment and security contract rather than a widened loopback server.
Hosts may further restrict the declared CSP. Codex desktop 26.825.32147 removes
all `http:` frame domains while building its sandbox CSP, so it blocks Leaf's
loopback frame with `ERR_BLOCKED_BY_CSP`; the automatic snapshot path is the
supported result there. The official reference host accepts the same exact HTTP
origin, so this is not a universal MCP Apps restriction and does not justify a
second local HTTPS transport.

## Snapshot fallback

`leaf_present_snapshot` is a separate model-visible tool, but it binds the same
adaptive resource. It is an explicit fallback, not the primary interface and not
a compact vocabulary projector. It renders inert authored markup and theme
rules, supports page, element, and passage comments, and offers the ordinary
browser route when one exists. `leaf_snapshot_refresh` is app-only and read-only.
`leaf_snapshot_apply_event` is the only write-annotated MCP tool because it
durably appends a reader comment. Its server boundary admits only `comment`
events before delegating to the shared event endpoint; app-only visibility and
the browser bundle are not write authorization for any other registry kind.

The append gate canonicalizes abbreviated text anchors before storing them, so
fallback clients do not create weaker durable anchors. Served runtime anchors
keep the browser reading that already resolved them; only the snapshot endpoint
requests file-side capture. Snapshot mode runs no authored code and does not
implement package actions. It removes authored navigation, editing, and form
targets, cancels composed link and form defaults, and applies containment rules
after authored CSS so snapshot content cannot replace the app document or cover
its controls. The old single-choice `lf-options` projector is deliberately
absent: a fixed shape was a second Leaf interface and understated what the
complete route can carry.

## Return and wake

Both modes persist reader gestures before reporting success. Neither calls
`ui/message` to claim delivery or advances the event cursor from an MCP response:
the host may accept that JSON-RPC request without starting or durably queueing a
turn. `leaf codex start <page>` remains the authoritative return carrier. Its
detached adapter waits on the same log, queues an exact persisted batch into the
same Codex task, and acknowledges only after durable queue acceptance.

The tracked adaptive bundle is generated from `scripts/mcp-app/` by
`scripts/vendor.py mcp-app`; do not patch the generated HTML under
`assets/vendor/` directly.
