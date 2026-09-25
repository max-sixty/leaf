# Frame-edge margins through transparent wrappers

The shared `--lf-block-frame` rule trims the first and last authored **direct** children of a framed box. A child margin can collapse through a transparent wrapper and still add to the frame's apparent inset. The render gate's `trappedMargins` reading also inspects only direct children, so such pages pass. The first-Ask heading case is one instance of this boundary mismatch.

## Rendered controls

- In `alert-review`, deleting the page's `#ar-alerts > section:first-child > h3 { margin-top: 0 }` rule moves the heading 32px below the pane's 14px top inset. The local rule currently hides the defect.
- A final Ask containing a playground, swipe deck, or targeting widget adds 24px below the page's declared 96px bottom inset in `data-explorer`, `ideas-to-implement`, and the targeting gallery. A symmetric Ask-only trim removed the gap in all three during the audit, but it was not kept because the same leak occurs through many other wrappers.
- In the `root-tabs` regression page, `#plan-tab` draws 24px of top padding but its heading starts another 48px lower through a section. A recursive edge-trim prototype put the heading at the 24px inset and left the next section's 48px heading margin intact.
- In `heat-loss`, the last chart's 14px margin crosses its section and makes the page's 96px bottom inset appear as 110px.
- The similar zero-margin rules on the site homepage do not change its current geometry when removed: its preceding hero already has a larger margin. They are not evidence of this defect.

## Sweep

A temporary recursive version of `trappedMargins` reported frame-edge margins in 13 of 24 shipped and regression pages while the Ask-end trim was active. The three final-Ask gaps above are additional cases. These probe reports are candidates for rendered review, not 13 confirmed visual defects:

| Edge | Pages reported by the probe |
| --- | --- |
| At least one top edge | `current-proposed-comparison`, `review-queue`, `root-tabs` |
| At least one bottom edge | `heat-loss`, `live-progress`, `log-retention`, `pr-walkthrough`, `release-notes`, `review-a-plan`, `rust-sort`, `security-boundary`, `swipe-gallery`, `feature-gallery` |

A CSS prototype that recursively trims every first or last descendant clears the measured section and tab gaps, but changes margins on 41 corpus elements, including elements inside formatting contexts such as `lf-command` and `lf-task`. Those margins are not passed to the outer frame. The general rule would change unrelated widget spacing.

The next implementation should carry frame-edge context only through wrappers that explicitly delegate their edge spacing to the frame. The render gate should follow the same path and report an untrimmed margin where a framed box draws its inset. Add rendered cases for a transparent wrapper, a formatting-context stop, a padded nested frame, and a later sibling whose normal spacing must survive; then sweep the reported pages and update the owning examples or components.
