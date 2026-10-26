Make a compact decision page for the Atlas search rollout. EU is paused because
its freshness lag is 11 minutes against a 5-minute limit. I need to compare
these options and choose exactly one on the page:

- Resume EU now: reaches all workspaces sooner, but publishes stale results
  until the backfill catches up.
- Hold EU until the 16:00 UTC checkpoint: keeps the current rollout elsewhere
  moving while Mira measures the backfill, but delays EU users.
- Roll back EU: restores the old index there today, but requires a second
  rollout after the backfill problem is fixed.

The current recommendation is to hold until the checkpoint. Keep the evidence
beside the choices, make the selected option apparent after I choose it, and do
not say that the choice performs a rollout operation.
