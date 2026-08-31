# Experiment 27: Stable fullscreen control and Axe detail

## Purpose

Preserve the host's display-mode capabilities across partial context updates and
identify the exact node behind the one remaining Axe finding.

**Changes from experiment 26:**

- Update fullscreen availability only when a host-context notification actually
  carries `availableDisplayModes`.
- Include Axe's full violation report in the recorded result.
- Keep the server, cookie, fixture, modes, and keyboard interaction unchanged.

**Expected outcomes:**

- `Return inline` remains visible after the resize-only host notification.
- Fullscreen and durable-event evidence stay green.
- The Axe report names the concrete element requiring either a fix or an
  evidence-backed explanation.

## Findings

The fullscreen fix held: after the host's resize-only context notification,
`Return inline` remained visible. Full rendering, dimensions, and the durable
keyboard event stayed green.

Axe's one moderate finding targets `.lf-banner-status`: the injected status text
is outside a landmark because the top Leaf chrome is a generic `div`.
Experiment 28 changes that existing top chrome to a semantic `header` and checks
the composed app again.
