Lead with the release's current state: what is live, what stopped it or what comes next,
and any hold or escalation policy and deadline. Keep the supporting measurements, checks
and run log available, with observed values beside their required values. Keep reference
material from obscuring the state and the operator's next decision. Write the release's
identity and summary in the markup, so a feed update can't change the page's conclusion.
For a live log the user follows, bound its height as `references/page-layout.md`,
"Bounds and widths", describes.

When rollback needs the operator's decision, ask beside the current state: an `lf-ask`
whose heading asks whether to roll back, holding an `lf-options choose` group with a
rollback option and the alternative the release policy allows, such as holding until
the deadline. Name the exact candidate and stable releases in the rollback option, and say
what choosing it does. The pick reaches the coordinator as the operator's answer. Don't
offer a button that looks like rollback but does nothing.
