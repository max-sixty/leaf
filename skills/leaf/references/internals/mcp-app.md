# MCP App transport

Status: experimental. This transport is merged to test the embedded review in
installed Codex builds. Its inclusion does not commit Leaf to retaining it or
expanding it toward browser parity; that decision follows from real use.

Leaf's bundled stdio server is a host transport over the existing page model.
It never owns current state: `index.html` starts state, immutable revisions hold
valid saves, `comments.jsonl` changes them, and the page transaction remains the
only read/write boundary. `PageStateService` is shared by HTTP and MCP so those
transports cannot drift into different projections.

The Codex manifest points at `.codex-plugin/mcp.json`, which launches `bin/leaf
mcp` from the installed plugin root. Keeping the config off the root `.mcp.json`
path prevents Claude Code from auto-registering this Codex transport. The server
exposes one model-visible presentation tool,
`leaf_present`, and one `ui://leaf/review/v1.html` resource with
`text/html;profile=mcp-app`. The tool's ordinary content and structured result
contain only a small summary. Authored HTML, theme, current projection basis,
and the pending event batch live under result `_meta.leaf`, which the host sends
to the app but does not put in model context. The card identifies this as an
authored snapshot; projected widgets, threads, and package interactions belong
to the full browser.

The compact app always exposes **Full page**. It opens the live page through
`ui/open-link` when a server URL is present and the host supports links;
otherwise it uses `ui/message` to ask the task to start the full browser flow.

Three app-visible tools complete the loop:

- `leaf_apply_event` sends one attempt-identified event through `EventEndpoint`;
- `leaf_refresh` takes a fresh authoritative snapshot;
- `leaf_delivery_ack` advances the cursor after the host accepts a follow-up.

The app must persist an event before asking the host for a new turn. It first
offers the exact batch through `ui/update-model-context`, then calls `ui/message`;
if the host refuses hidden context, it includes the batch in that message. It
best-effort clears accepted model context after that follow-up, then acknowledges
once the follow-up itself is accepted. A clear refusal cannot turn a known delivery
into a retry and duplicate the turn. A failed follow-up leaves the batch pending and
offers a retry. This is the same at-least-once page-and-sequence contract as the
detached adapter.

The resource is self-contained and declares no network or external-resource
domains. It strips executable document content, uses a shadow root for authored
markup and theme rules, disables page controls, and supports comments only. Do
not point an iframe at Leaf's dynamic loopback URL or grant a wildcard CSP to
recover the full runtime. Package-owned actions stay in the browser until the
runtime has a transport-independent bundle rather than a second implementation.
Passage comments are revalidated under the append transaction against Leaf's
file-side current passage reading; widget source and any anchor that would
detach are refused before append.
