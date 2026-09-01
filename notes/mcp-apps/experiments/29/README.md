# Experiment 29: Comments and version travel in the full app

## Purpose

Exercise the two page-level systems most likely to expose a false “full Leaf”
claim: anchored comment creation and navigation between immutable versions.

**Changes from experiment 28:**

- Give the decision page two stamped versions whose opening sentence differs.
- Create an anchored comment on text shared by both versions from inside the MCP
  App.
- Navigate v2 → v1 → v2 through Leaf's own version menu and measure the anchor
  highlight on both.

**Expected outcomes:**

- The comment appends through `/api/event` with its ordinary passage anchor.
- Both historical navigations remain authorized by the partitioned session.
- The thread quote and highlight resolve on v1 and v2, while the surrounding
  changed sentence proves the document actually traveled.

## Findings

The composed app authored the normal sequence-4 comment at revision 2 with
Leaf's `{section, quote, prefix, suffix}` anchor. Its quote and one painted
highlight remained resolved after navigating to
`/versions/v1.html?pin=` and back to `/versions/v2.html?pin=`, while the changed
`split`/`extraction` sentence proved the document actually changed.

The earlier full-page evidence remained green: both display modes, zero Axe
violations, the visible return control, and the Redis action persisted alongside
the comment and version travel.
