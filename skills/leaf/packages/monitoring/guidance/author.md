Build a release page as a body beside a side track, `<main class="layout-sidebar">`.
Lead with the release's current state in the lede and a callout: what is live, what
stopped it or what comes next, and the hold or escalation policy with its deadline.
Open the body with the headline numbers as `lf-metric` tiles in a `layout-tiles` block,
and put the evidence the state rests on under them: the run log, bound with
`data-bound="end"` so it stays on its newest line, beside the named checks with their
observed and required values in the side track. Keep the release identity, steps,
notes, owners and rollback procedure in the side track or below in ordinary flow, with
the reference material in `details`. Keep release identity and summary in
authored markup so a feed update cannot silently change the page's conclusion.

When rollback is genuinely available, ask for it beside the current state: an
`lf-ask` whose heading asks whether to roll back, holding an `lf-options choose` group
with a rollback option and the alternative the release policy allows, such as holding
until its deadline. Name the exact candidate and stable releases in the rollback
option and state its consequence. The pick reaches the coordinator as the operator's
answer. Do not present a decorative button as rollback.
