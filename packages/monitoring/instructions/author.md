Build a release page as `<main class="layout-sidebar">`, with the `aside` written after
the body. Lead with the release's current state in the lede and a callout: what is live,
what stopped it or what comes next, and the hold or escalation policy with its deadline.
Open the body with headline numbers as `dl` elements in a `layout-tiles` block, then the
evidence the state rests on: the run log in the body, and the named checks with their
observed and required values in the `aside`. Put the release's identity, steps, notes,
owners and rollback procedure in the `aside` or lower in the body, with reference
material in `details`. Write the release's identity and summary in the markup, so a feed
update can't change the page's conclusion. For a live log the user follows, bound its
height as `references/page-layout.md`, "Bounds and widths", describes.

When rollback is possible, ask for it beside the current state: an `lf-ask` whose
heading asks whether to roll back, holding an `lf-options choose` group with a rollback
option and the alternative the release policy allows, such as holding until the
deadline. Name the exact candidate and stable releases in the rollback option, and say
what choosing it does. The pick reaches the coordinator as the operator's answer. Don't
offer a button that looks like rollback but does nothing.
