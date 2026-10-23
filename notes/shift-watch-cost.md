# Shift-watch cost

`tests/shift_watch.js` owns the Stability sensor and explains why Chrome's
layout-shift source rectangles cannot replace its landmark ledger. Its header
also describes the current reuse of unchanged readings. This note holds cost
evidence and remaining optimization work; `tests/AGENTS.md` owns test selection.

## Idle cost

The sensor's frame loop and paint checkpoint keep requesting frames on a still
page. In two October 2026 CI jobs, this cost 0.03–0.05 s of main-thread time and
0.04–0.065 s of CPU across processes for each second the page stayed open.
Rerun those historical measurements before estimating current savings.

## Open findings

- **Coverage exemptions need review.** Whether each `shifts_unsurveyed` module
  still needs its exemption hasn't been reviewed. Measure the cost of watching
  the affected tests before widening coverage.
- **The idle cost has a fix that changes the watch's self-check.** Stopping the
  frame loop while nothing is announced or running, and restarting it on the
  next announcement or layout-shift entry, would let a still page stop rendering.
  The VERIFY reading would then run only at judgement rather than every 30th
  quiet frame, so the user would decide whether that self-check is worth the
  idle cost.
- **Unconfirmed: a reading may lay a frame out twice.** `tick` runs in the frame's
  first callback, before the page's own frame callbacks write, so where those
  write, the browser may lay the frame out once for the reading and again to
  paint it. Reading after layout would change which pose a frame records, which
  the ledger's frame pairing rests on.
