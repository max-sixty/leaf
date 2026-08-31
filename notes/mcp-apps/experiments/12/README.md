# Experiment 12: Contain and clarify evidence

## Purpose

Repeat experiment 11 after its measurements showed that evidence expanded the
document and used insufficient contrast on the host's option-panel color.

**Changes from experiment 11:**

- Fix the app shell at the iframe viewport height so the middle grid row owns
  scrolling and the footer remains visible.
- Use the primary text color for decision evidence.

**Expected outcomes:**

- No document overflow; the content row scrolls vertically at 420×360.
- The visible footer status remains inside the 354-pixel app viewport.
- Axe reports no violations.
- Evidence and keyboard append behavior remain unchanged.

## Findings

The two CSS changes resolved both measured defects. In the 414×354 app viewport,
the document's client and scroll dimensions were identical, while the middle
content row held a 270-pixel viewport over 526 pixels of complete option content.
All three short labels and all three evidence summaries remained present. The
footer stayed in the fixed shell and exposed a real 15-pixel-high status box
after the choice.

Axe reported zero violations. Keyboard Enter appended the same ordinary
`session-options` / `choose` / `opt-redis` event at sequence 1. The only console
error was again the official reference host's missing favicon. This is the first
run in which the evidence-bearing compact surface, containment, contrast,
visible feedback, accessibility scan, and durable return path all passed
together.
