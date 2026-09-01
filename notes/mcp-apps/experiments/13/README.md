# Experiment 13: Final generated bundle

## Purpose

Repeat experiment 12 against the exact bundle left by the formatter, two
byte-identical vendor builds, parser cleanup, and full-suite review.

**Changes from experiment 12:**

- Product behavior is unchanged; record the final bundle's SHA-256 beside the
  same reference-host, axe, layout, evidence, and keyboard readings.

**Expected outcomes:**

- Experiment 12's results repeat against the exact bytes being handed over.
- The recorded hash matches the twice-reproduced vendor output.

## Findings

The final generated bundle passed the same complete reference-host measurement.
Its SHA-256 was
`bd8134f2622641ae37512dcf7108b4ccccb5bed03bd842f89800e794272effd7`,
matching both reproducibility builds. At 414×354 the document had no overflow,
the evidence row scrolled internally, all three complete summaries remained,
axe reported zero violations, and keyboard Enter appended the ordinary Redis
choice at sequence 1. The only console error remained the reference host's
missing favicon.

This run exercised the exact HTML bytes left in the worktree after formatting,
review fixes, and the 740-test everyday suite.
