Build a release page as a document with grids. Lead with the release's current state in
the lede and a callout: what is live, what stopped it or what comes next, and the hold
or escalation policy with its deadline. Put the headline numbers in an `lf-grid` of
`lf-metric` tiles, and the evidence the state rests on beside itself in a second grid:
the named checks with their observed and required values in one cell, and the run log
in the other, bound with `data-bound="end"` so it stays on its newest line. Keep the
release identity, steps, notes, owners and rollback procedure below in ordinary flow,
with the reference material in `details`. Keep release identity and summary in
authored markup so a feed update cannot silently change the page's conclusion.

When rollback is genuinely available, put one `lf-release-actions` holder around an
`lf-release-action verb="rollback"` beside the current state; bind the holder to the
exact candidate and stable release, and state the consequence in the action's prose.
This sends a durable host request and waits for its receipt. Do not present a local
choice or decorative button as rollback.
