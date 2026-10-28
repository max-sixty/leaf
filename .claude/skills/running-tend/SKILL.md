---
name: running-tend
description: Project-specific instructions loaded by tend workflows alongside AGENTS.md.
---

# Running tend — leaf

## Landing

Tend uses `merge: yolo`. **Fixing a CI failure's cause** defines when a CI
repair can land without maintainer approval.

Changes to workflows, Tend's configuration, CODEOWNERS, or agent instructions
require the control-plane owner's fresh approval.

Merging squashes with `PR_TITLE` / `PR_BODY`, so the description becomes `main`'s
commit message; hold its claims to the standard the diff is held to.

## Review threshold

Apply `AGENTS.md`'s **Stage** and **Fix the underlying issue** sections and
`/developing-leaf`'s **Weigh what a change adds** to the verdict; most of Tend's own
pull requests land on this review alone. Once a change moves Leaf toward a coherent
architecture, its claimed path works and what it adds is worth keeping, the review
is done. Reserve findings for architectural seams, cross-runtime invariants, public
surface traps, regressions anywhere the change reaches, additions that cost more
than they buy, or a central claim or test that is false or that nothing has shown.
Omit bounded edge cases, exhaustive same-pattern cleanup, minor simplification, and
prose or test polish unless they expose one of those problems. Those findings ask a
change to cover more or read better; a finding that it adds more than it buys is
none of them.

The verdict rests on that weighing. Weigh the change before searching it for
defects, and revisit the weighing when a defect shows a cost it missed: on Tend's own
pull request a defect found in an addition gets fixed and the addition lands, so for
an addition the weighing rejects, the rejection is the finding, not its defect. State
in the session what the change adds that later changes must hold, what that buys, who
pays its cost and who gains beyond the claimed case, and the cheapest other change
you can name that buys the same. Where that change keeps what this one must and costs
materially less, it is the finding: withhold approval and name it.

In shipped text (the references, `--help`, UI strings, `SKILL.md`, and the agent
instructions in the `AGENTS.md` files and `/developing-leaf`), these prose defects
are public surface traps: mechanism written for a reader other than the one the text
addresses, a second copy of a rule another text owns, a coined term used without its
definition, and, in maintainer guidance, a sentence that says how the diff's code
works or which failure it fixed rather than what other code must rely on. Ask for
that sentence to move to the module header or the commit message.

A diff that settles its symptom without reaching the underlying issue is an
architectural seam: name the issue, and withhold approval unless the change meets the
deferral condition in **Fix the underlying issue**. A fix for a red test that moves
the interface beyond what the breaking change meant to, or gives up that change's
intent without the issue **Reading a red suite** requires, is a regression.

## Review test selection

Before approving a product change, select and run focused checks through
`tests/AGENTS.md`, **Selecting checks**, covering the changed behavior and its
consumers. A docs-only or generated-workflow change may need none.
A failing selected test or PR check withholds approval only
when the change causes it: confirm an inherited failure against current `main` per
`/tend-ci-runner:monitor-ci`, record that evidence in the review, and approve when the
change has no other findings; "Run what the change needs" governs landing despite that
failure. Where a test itself is at issue, `tests/AGENTS.md` says
which boundary it belongs at. For a change that can alter browser startup, apply
`AGENTS.md`'s **Working on the repository** performance rule to the candidate and base
profiles from CI.

A CI repair that changes what a page draws, such as its CSS, layout or a widget's
rendering, names in its description the states it changes on screen. Before the
verdict, its review captures each of them on the base and the head with
`uv run leaf-dev stills --state NAME`, adding a state to its `STATES` where none
reaches the surface, looks at the crops, and weighs what changed against every
state that pays for it. Without captures it can read, the review withholds approval.

## Explaining UI changes and questions

Include screenshots when explaining a UI change or asking the maintainer to judge
an interface. Put the visual evidence in the PR description or reply where the
change or question is presented, so the reader can inspect the affected state
before answering. Show before and after for a change, and the relevant alternatives
for a design question. Follow `/developing-leaf`, **Prove and hand off a visible
change**, for capture and delivery.

## Reading a red suite

When a change turns a test red, merged or still in a pull request, the change and
the behavior the test protects disagree. Choose the repair by what it keeps of each:

- **The change's intent**: what its author meant it to do, read from the pull
  request's description, discussion and diff. Undoing part of it reverses a
  decision someone made.
- **The interface**: what users see and do, and what callers rely on, such as a
  gesture's effect, a layout, a command or a file format. A repair that moves it
  further than the change meant to makes a product decision nobody asked for.

The existing assertion is evidence about both, not authority (`tests/AGENTS.md`,
**Failing tests**). Prefer a repair that keeps both:
update the test whose expectation the change replaced, or fix the code so the
change's intent holds without moving the interface further. Where no repair
keeps both, revert the change, or the part of it at fault. When the test itself is
wrong, validate the intended behavior with corrected or replacement checks, and
justify removing a test that protects no user behavior rather than claiming it
passed.

A repair that gives up any of the change's intent, or was chosen where the evidence
left the choice uncertain, needs an issue so the change can return deliberately.
Address it to the change's author; when a bot wrote it, to the person who requested
or merged it, or to the repository's maintainer where no person did. Link the
originating and repair pull requests, and say what the change intended, what
conflicted, what the repair gave up and what remains uncertain. Mark the issue as
awaiting that person's judgment and leave it open until they settle it; later Tend
runs must not decide on their behalf. The repair's description names each behavior it
moved. Proceed under **Fixing a CI failure's cause** without waiting for that
judgment.

Before choosing a fix, read the failing test's record in main's earlier runs: each
`ci` run uploads its junit results (`gh run download <run> -p 'pytest-results-*'`),
with the failing pages' pictures (`tests/AGENTS.md`, **Failing tests**), and a
`nightly` test runs only in the daily scheduled run (`gh run list -w ci -e schedule`).
A test that failed with the same message, passed on code that didn't fix it, then
failed again is non-deterministic, so fix the cause.
A watch finding that fails on CI and passes locally needs a slower CPU rather than
reruns to reproduce (`tests/AGENTS.md`, **Races**).
Different messages across runs call for checking the intervening changes and the
behavior each failure caught; simplify a test that unrelated changes repeatedly break
without changing that behavior.

Two test-owned failures recur:

- **A read or press before the page said it was ready**, which a re-run hides.
  State the ordering (`tests/AGENTS.md`, **Races** and **Transient states**) rather than repeating the gesture.
- **A reading that has been widened before.** When the fix that presents itself
  is one more member of an accepted set, allowlist, or tolerance, read the line's
  history (`git log -L`); a set that keeps growing describes the suite's own
  noise, and the fix is against the test (`tests/AGENTS.md`, **Test-made noise**).

## Fixing a CI failure's cause

A cause issue (`tend-ci-cause`) records the first `ci` run on main its tests
failed in, with its commit, since that brackets the change that broke it; a
`journeys` test, like the whole `test-macos` job, runs only nightly, so the pull
request that broke it usually passed its own CI. Before fixing, check current main:
the complete suite takes hours, and later changes may have removed the cause. A passing rerun
alone does not clear a failure that comes and goes.

Establish the conflict before applying **Reading a red suite**'s revert-and-decision
route. An unresolved diagnosis or a missing verification environment remains
engineering work, owned by the cause's session through `/tend-ci-runner:triage`'s
**A cause issue** route.
For a local website gate the sandbox cannot run, `worker/README.md`, **Local
development**, gives its non-deploying CI route.

For each durable failure, look for the pull request that introduced it, first
among those merged since the last run where the failing check passed and then
earlier, since a failure that comes and goes can pass after its cause landed.
Where the runs' records leave the range wide, `git bisect run` over the test's node
id finds the commit. Establish the cause from the failing diagnostic and the pull
request's context, following **Reading a red suite**, and link that pull request
from the fix's description with the behavior its author intended and why the repair
changes the test or the behavior.

Merge a pull request that fixes tests, without waiting for maintainer approval,
once each test it claims to fix failed before the change and passes after it
(a skipped or deleted test has not passed). Pull requests run only the later-tier
tests they edit, so run the claimed ones yourself. The pull request's CI must
reach a terminal result on the exact head (`monitor-ci`). A failure there outside
the tests it claims, and not caused by its change, neither blocks the merge nor
calls for a rerun: the report for that run carries it to its own cause. GitHub's
applying merge rules still govern the merge.

Merge a fix that is correct but incomplete, and open an issue for what it leaves.

## A red `ci` on main is live

A red `ci` on main affects whoever pulls next, so treat it as live
(`tests/AGENTS.md`, "Run what the change needs", says what each trigger runs; every
`test` job also runs `pnpm run check`).
Pushes to main hold one suite slot and a newer commit replaces the one waiting,
which GitHub records as a cancelled run whose `test` job has no runner (`runner_id`
0); that is not a regression. A `test` that held a runner and still ended cancelled
hit its timeout, and that is a failure.

The scheduled run's `test-macos` job runs every tier on macOS, which your Linux runner
can't reproduce. For a failure only that job shows, the failing run is the evidence
from before the fix. For the evidence from after it, dispatch `ci` on the fix's branch
(`gh workflow run ci --ref <branch>`) and read that run's `test-macos` job.

## Cloudflare logs

`CLOUDFLARE_API_TOKEN` is the `Leaf observability (Tend CI)` token in
`worker/README.md`: it reads the deployed site's Workers Observability logs and
Analytics Engine events and cannot deploy. It is set only for an agent answering
an issue, including a CI failure report and its cause issues. When an issue or a
red `publish-site` concerns
the deployed site, diagnose from those records as the README describes. Drop the
token from any command that runs a pull request's code with
`env -u CLOUDFLARE_API_TOKEN`.

## Filing issues in other repos

Permanent exception granted: file directly in agent-equipped targets (per
**Filing issues** in the bundled `/tend-ci-runner:act-in-other-repos` skill)
without asking permission here first. The default rule (open an issue here asking
permission first) still applies when the target shows no agent signals.

## Leave outage trackers for the drain

Leave a **"Bot temporarily unavailable"** tracker open until `tend-review-runs`
drains its rows, whatever its body says, since each row names a stranded
trigger. This applies by title; a CI failure report names no stranded trigger,
and its lane's next passing run closes it.

## Leave backlog issues to the maintainer

An issue labelled `backlog` is an item on the maintainer's prioritised backlog
(`TODO.md` says how it is kept), not a report awaiting triage. When one reaches
you, whether through triage or an unread notification, take no action, post
nothing, and acknowledge the notification.

## Nightly: model and harness releases

Keep Leaf's model defaults current and find upstream capabilities worth adopting.
Each nightly run, scan the
[Claude Platform release notes](https://platform.claude.com/docs/en/release-notes/overview),
[OpenAI API changelog](https://developers.openai.com/api/docs/changelog),
[Claude Code changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md),
[Codex releases](https://github.com/openai/codex/releases), and
[Codex product changelog](https://developers.openai.com/codex/changelog/).
Read entries since the last successful `tend-nightly` run, with a day's overlap;
on the first run, read the past week. Report a source that cannot be read in the
run summary rather than treating it as having no changes. Search open and closed
issues and pull requests first, and skip changes already covered, adopted, or
declined.

### Model defaults

Compare the current defaults with each provider's current stable models, even
when a release predates the scan window. `MODELS` in `dev/leaf_dev/arms.py` owns
the eval agents, judges and simulated user; the website adapter in
`worker/leaf_website/` owns its hosted default, and `.config/tend.yaml` owns
Tend's. Change these owners, not model names throughout the tree.

Prepare a pull request upgrading a default to its suitable stable successor,
preserving each role's purpose and weighing quality, latency and cost; a newer model
in a different tier is a candidate to evaluate, not an automatic replacement.
Verify the exact model id and availability through the actual harness and login,
and run a small representative eval or journey for the affected role, including
grading when a judge changes. Record the old and new models, upstream sources
and validation, and keep model pins the same across arms in a Leaf comparison.
Regenerate Tend workflows from its config when Tend's default changes, and follow
**Landing** for changes requiring the control-plane owner's approval. If access
or a material tradeoff prevents a bump, report what remains to establish.

### Harness opportunities

Look for concrete, material opportunities or incompatibilities in Leaf's current
code or agent workflow, including new capabilities that could simplify Leaf or
improve its user experience, and check the affected implementation and upstream
documentation before deciding. Releases touch Leaf's harness integration through
hooks, waking agents, background work, plugins, MCP and permissions, but a release
that mentions one does not by itself justify an issue.
Claude Code's `asyncWake` is the calibration example: a harness capability that
could improve Leaf's comment-to-agent wake loop warrants investigation. Routine
fixes, cosmetic changes, and speculative relevance do not. Expect a qualifying
finding on roughly 5% of days; this is a relevance threshold, not a quota or a reason
to withhold an important finding, and it does not limit model-default bumps.

For a qualifying finding, open an issue here rather than implementing it as part of
the scan. Include the upstream version or date and source link, the affected Leaf
code or workflow, the concrete benefit or breakage, and a proposed next step, and
distinguish confirmed behavior from an integration hypothesis. When nothing
qualifies, keep the result in the run summary; do not post a digest.

## Nightly: regular maintenance

In the rolling survey, apply `/developing-leaf`, "Regular maintenance", to each file
you review. Propose a removal that takes a feature away in an issue for the
maintainer; a consolidation or delegation that keeps behavior is an ordinary fix.

## Weekly: test tier budgets

Read the latest daily `ci` run that finished (`gh run list -w ci -e schedule`): its
`test` job's summary lists the tests over their directory's budget and the journeys
within the browser budget (`leaf-dev suite-profile`). A test over budget in two daily
runs either moves to `tests/journeys/` or gets faster; a journey within the browser
budget in both moves to `tests/browser/` when its boundary is one page. A single
reading moves nothing, since one run's time includes contention. Open one pull
request with the moves, listing each test and the times behind it.

## Weekly: interface sweep

Run `/ui-sweep` before dependency maintenance, following its **Reconcile** route:
a reproduced defect becomes a tested repair, and a design judgment stays in the
run report.

## Weekly: vendored browser dependencies

Dependency automation rebuilds committed browser bundles on Dependabot's PR.
Read each `*.LICENSES.txt` diff: a package listed at two versions means the bump
split a closure (Shiki's packages pin each other exactly);
`pnpm update <package> --no-save` moves a locked dependency within its dependant's
range. Drop a Lit bump the Web Awesome build refuses. Bump `esbuild` by hand when a
bundle needs it, and rebuild everything.
