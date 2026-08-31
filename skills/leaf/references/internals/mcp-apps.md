# MCP Apps delivery

MCP Apps is an optional local delivery surface, not Leaf's document or
interaction interface. The experimental server starts with `leaf mcp run` over
stdio. It is not registered automatically by either plugin manifest.

## Authorities and lifetime

Every tool call names an initialized page directory. Authored markup remains the
initial condition and `comments.jsonl` remains the only transition record. No
MCP tool or iframe owns current state, replay, undo, versions, or comments.

`leaf_open_page`, `leaf_read_page`, and both compact reads activate and read
inside Leaf's ordinary page transaction. A valid changed `index.html` may
therefore create the next immutable revision, so these tools do not advertise
the MCP read-only hint despite returning a projection. Closing an app discards
only its view. Opening it again reconstructs from the page directory and log.

The full-page server is process-scoped plumbing. It starts one ephemeral
loopback HTTP server per opened page, reuses it for later calls, writes no
`service.json`, and stops with the MCP process. The page directory and log keep
their normal lifetime; the loopback address does not.

## Complete page

`leaf.page/v1` addresses Leaf's ordinary browser interface. The `ui://` app is a
small host-themed shell containing Refresh, Open in browser, and negotiated
inline/fullscreen controls. Its nested iframe loads the same projected document,
vendored layer, widget modules, comment UI, version navigation, state stream,
and `/api/event` endpoint used by a normal Leaf tab. This is delivery of the
existing interface, not a second renderer.

The app resource declares `http://localhost:*` in `frameDomains`. Its ephemeral
server binds only `127.0.0.1` but presents a `localhost` URL so Chromium accepts
the secure-loopback cookie exception. Ordinary Leaf servers retain
`SameSite=Strict`; only this third-party app server sends its random,
page-server-scoped token as `SameSite=None; Secure; Partitioned`. The token dies
with that MCP process rather than exposing Leaf's durable machine-wide host key
in an MCP tool result. It keeps authentication on assets, state, and event
writes while isolating the cookie by the MCP host's top-level site.

This path is local-host-only. The browser rendering the MCP App must share the
machine running `leaf mcp run`; a cloud host's `localhost` is not the MCP
server. A future remote page address needs an explicit deployment and security
contract rather than silently widening this server.

## Compact projection

`leaf.compact-ask/v1` is an optional small surface, not a restriction on the
complete app. It recognizes exactly one current, page-scoped, single-choice
`lf-options` ask inside its decision surface. It keeps the decision and
action-owning widget as separate addresses, derives the question from the one
direct heading, and retains every option's complete spoken text as evidence.

No ask produces an empty state. Several asks, thread asks, multiple choice,
unknown vocabularies, unresolved addresses, unreadable headings, and invalid
mutable source produce an explicit fallback. They are never flattened or
guessed. A compact press calls the app-only `leaf_post_event`, which sends the
browser-shaped event through `EventEndpoint` and returns the transaction's new
projection. It does not append directly or keep an MCP replay list.

## Tools and resources

- `leaf_open_page` is model-visible and opens `ui://leaf/page.html` with a
  `leaf.page/v1` result.
- `leaf_read_page` is app-only and refreshes that complete-page address.
- `leaf_open_compact_ask` is model-visible and opens
  `ui://leaf/compact-ask.html` with a `leaf.compact-ask/v1` projection.
- `leaf_read_compact_ask` and `leaf_post_event` are app-only compact return
  tools.

Both resources use `text/html;profile=mcp-app`. Their tracked sources live under
`scripts/mcp-app/`; `scripts/vendor.py mcp-app` bundles the pinned official SDK,
application code, styles, and existing Leaf mark into committed standalone HTML
files under `assets/vendor/`. The complete-page shell alone declares a framed
origin; neither shell loads its own code or styles from the network.

Keep registration separate from this contract until shipped-host experiments
establish launcher configuration, local-frame policy, cookie behavior, and
startup cost. The portable primitive is the stdio command. `ui/message` wake
behavior is also host policy and is not part of either event return path.
