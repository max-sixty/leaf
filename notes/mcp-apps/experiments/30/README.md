# Experiment 30: One exact origin with page capability paths

## Purpose

Test the production candidate for delivering the complete canonical Leaf page:
one loopback origin registered exactly in MCP Apps CSP, with each page isolated
under an unguessable path and no query credential or cookie.

**Changes from experiment 29:**

- Replace one wildcard-CSP HTTP server and partitioned cookie per page with one
  process-scoped exact origin and `/p/<capability>/` routes.
- Exercise the auto-registered `leaf_present` tool rather than the earlier
  `leaf_open_page` prototype.
- Remove the fixed single-choice compact MCP interface and keep the authored
  snapshot only as an explicit fallback.

**Configuration:**

- MCP Apps reference host: `modelcontextprotocol/ext-apps` at
  `10195ad91851502134930e9b80ec2c04e277a720`.
- Resource CSP: the ephemeral `http://localhost:<port>` origin exactly.
- Page address: queryless random capability path on that origin.

**Expected outcomes:**

- If the exact origin is sufficient, the nested frame reaches Leaf's presented
  state and a keyboard option action appends through the ordinary event endpoint.
- If the host rejects the origin or nested local frame, the outer app appears but
  the canonical page never reaches its presentation gate.
- Any request escaping the capability path or any Leaf-origin console failure is
  a routing defect.

## Findings

The exact-origin design passed in the pinned official reference host. The
resource declared one concrete `http://localhost:59857` frame domain and the
nested canonical page loaded from the same origin at the queryless random path
`/p/RjvO7cTim42U_745ZdE9Zk24azyZGz93/`. It reached
`data-lf-presented="1"`, negotiated fullscreen with a visible return control,
and a keyboard Redis choice appended the ordinary sequence-2 `choose` action to
`session-options`.

No warning or error came from the app or Leaf origins. The one console error was
the reference host's own missing `http://localhost:8080/favicon.ico`. Axe found
one moderate `region` violation when measured after the choice; experiment 29's
zero-violation measurement ran before its choice, so this result does not isolate
transport from interaction state and is not evidence against the exact-origin
route. Stratify that timing separately if accessibility parity becomes the next
question.
