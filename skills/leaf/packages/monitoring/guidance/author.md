Build a release page as a body beside its `aside`, `<main class="layout-sidebar">`
with the `aside` written after the body.
Lead with the release's current state in the lede and a callout: what is live, what
stopped it or what comes next, and the hold or escalation policy with its deadline.
Open the body with the headline numbers as `lf-metric` tiles in a `layout-tiles` block,
and put the evidence the state rests on under them: the run log, bound with
`data-bound="end"` so it stays on its newest line, beside the named checks with their
observed and required values in the `aside`. Keep the release identity, steps,
notes, owners and rollback procedure in the `aside` or below in ordinary flow, with
the reference material in `details`. Keep release identity and summary in
authored markup so a feed update cannot silently change the page's conclusion.

When rollback is genuinely available, put one `lf-release-actions` holder around an
`lf-release-action verb="rollback"` beside the current state; set the holder's
`candidate` and `stable` to the exact releases, and state the consequence in the action's prose.
This sends a durable host request and waits for its receipt. Do not present a local
choice or decorative button as rollback.
