# Experiment 28: Landmark-clean complete Leaf page

## Purpose

Resolve the exact Axe finding by giving Leaf's existing top chrome its native
header landmark, then repeat the composed app measurement.

**Changes from experiment 27:**

- Create `.lf-banner` as `<header>` instead of `<div>`.
- Add a browser regression assertion for that semantic element.
- Change no layout classes, contents, controls, app transport, or interaction.

**Expected outcomes:**

- Axe reports no violations in the complete nested Leaf frame.
- Inline/fullscreen dimensions and horizontal overflow remain unchanged.
- Fullscreen return and the durable Redis keyboard choice remain green.

## Findings

The composed page passed unchanged layout and interaction evidence with the new
header landmark. Inline remained 1060×332 and fullscreen 1068×806 over the same
2,857px document, with no horizontal overflow. `Return inline` stayed visible,
Axe reported zero violations, and the Redis keyboard choice again appended the
ordinary sequence-1 action to the page log.
