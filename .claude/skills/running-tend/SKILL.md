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

Apply `AGENTS.md`'s **Weigh what a change adds**, **Stage**, **The maintainer
decides** and **Fix the underlying issue** to the verdict; most of Tend's own pull
requests land on this review alone.
Once a change moves Leaf toward a coherent architecture, its claimed path works and
what it adds is worth keeping, the review is done. Reserve findings for architectural
seams, cross-runtime invariants, a public interface that misleads its user, the text
defects root `AGENTS.md`, "Where instructions live", lists, regressions anywhere the
change reaches, additions that cost more than they buy, or a central claim or test
that is false or that nothing has shown.
Omit bounded edge cases, exhaustive same-pattern cleanup, minor simplification, and
prose or test polish unless they expose one of those problems. Those findings ask a
change to cover more or read better; a finding that it adds more than it buys is
none of them.

The verdict rests on that weighing. Weigh the change before searching it for
defects, and revisit the weighing when a defect shows a cost it missed: on Tend's own
pull request a defect found in an addition gets fixed and the addition lands, so for
an addition the weighing rejects, the rejection is the finding, not its defect.

A diff that settles its symptom without reaching the underlying issue is an
architectural seam: name the issue, and withhold approval unless the change meets the
deferral condition in **Fix the underlying issue**. A fix for a red test that moves
the interface beyond what the breaking change meant to, or gives up that change's
intent without the issue **Reading a red suite** requires, is a regression.

## Issues a change finishes

A `backlog` issue left open once a change has settled it tells the next session
there is work still to do. So the review checks each change against the open
backlog: list the open `backlog` issues, and read each one whose subject the change
touches, with the pull requests that already name it, to learn what of it remains.

- Where the change leaves nothing of an issue to do, by finishing what remains,
  removing its premise or recording a decision against what it asks, the
  description says `Closes #N`, so merging closes it.
- Where it does part, the description says `Part of #N` and what is left, so the
  review of the last part can tell that it finishes the issue. A `Closes #N` for
  an issue the change only partly does becomes this.

On Tend's own pull request, edit the description (**Keeping PR titles and
descriptions current** in `/tend-ci-runner:open-pr`). On someone else's, ask in
the review, naming each issue and what is left, since its author owns the
description and may rewrite it. The ask doesn't withhold approval, since it changes
no code and an edit to the description starts no new review. Where nothing else is
found, approve with the ask as the review's body.

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
`AGENTS.md`'s **Working on the repository** performance rule to the head and base
profiles from CI.

A CI repair that changes what a page draws, such as its CSS, layout or a widget's
rendering, names in its description the states it changes on screen. Before the
verdict, its review captures each of them on the base and the head with
`uv run leaf-dev stills --state NAME` (its `--help` covers the scheme and window, and
the `dev/leaf_dev/states.py` header says when to add a state). It looks at the crops
and weighs what changed against every state that pays for it.
Without captures it can read, the review withholds approval.

## Explaining UI changes and questions

Include screenshots when explaining a UI change or asking the maintainer to judge
an interface: before and after for a change, and for a design question each
alternative, pictured as root `AGENTS.md` asks. Put them in the PR description or
reply that presents the change or question, so the reader can inspect the affected
state before answering. `/developing-leaf`'s **Prove and hand off a visible change**
covers capture.

Upload screenshots to GitHub with the CLI’s native attachments:

```bash
gh pr edit NUMBER --body-file .tmp/pr-body.md --attach .tmp/before.png --attach .tmp/after.png
```

Reference those local paths in the body’s Markdown images; `gh` replaces them
with uploaded asset URLs. For a reply, use `gh pr comment` with the same flags.
Read back the published body and open its image URLs to verify the evidence.

## Reading a red suite

When a change turns a test red, merged or still in a pull request, choose the repair
as `tests/AGENTS.md`, **Failing tests**, says.

The change's intent, read as **Failing tests** says, settles each case it covers. A
repair that keeps that intent leaves nothing uncertain and needs no issue; ask the
author only about a case the intent leaves open.

A repair that gives up any of the change's intent, or was chosen where the evidence
left the choice uncertain, needs an issue so the change can return deliberately.
Address it to the change's author; when a bot wrote it, to the person who requested
or merged it, or to the repository's maintainer where no person did. Link the
originating and repair pull requests, and say what the change intended, what
conflicted, what the repair gave up and what remains uncertain. Assign the issue to
that person and leave it open until they settle it; later Tend runs must not decide
on their behalf. The repair's description names each behavior it moved. Proceed
under **Fixing a CI failure's cause** without waiting for that judgment.

Before choosing a fix, read the failing test's record in main's earlier runs: each
`ci` run uploads its junit results (`gh run download <run> -p 'pytest-results-*'`),
with the failing pages' pictures (`tests/AGENTS.md`, **Failing tests**), and a
`nightly` test runs only in the daily scheduled run (`gh run list -w ci -e schedule`).
A test that failed with the same message, passed on code that didn't fix it, then
failed again is non-deterministic, so fix the cause.
A watch finding that fails on CI and passes locally needs a slower CPU rather than
reruns to reproduce (`tests/AGENTS.md`, **Races**).

The issues that name the test, such as its cause issues and CI failure reports, say
what broke it each time, and the pull requests that closed them say what each repair
changed. Merged pull requests that name it add the repairs made without an issue.
Search both by the test's function name, and read the diagnoses and the repairs they
link:

```bash
gh issue list --state all --limit 100 --search "<test function>" \
  --json number,title,labels,closedByPullRequestsReferences
gh pr list --state merged --limit 100 --search "<test function>"
```

Where the test keeps failing, compare what each failure caught and what each repair
changed, and ask whether a fix in the test, or in the code it exercises, would end the
failures rather than this one (`tests/AGENTS.md`, **Failing tests**; `AGENTS.md`, **Fix
the underlying issue**). Where one would, make it instead of repairing this instance
once more.

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
alone doesn't show that a failure that comes and goes is fixed.

Establish the conflict before applying **Reading a red suite**'s revert-and-decision
route. An unresolved diagnosis, or a verification environment you can reach another
way, remains engineering work while the session has a step left to take, owned by the
cause's session through `/tend-ci-runner:triage`'s **A cause issue** route.
For a local website gate the sandbox cannot run, `worker/README.md`, **Local
development**, gives its non-deploying CI route.

A cause waits on the maintainer when its next step is one only they can take, such
as a decision. Say in it what you found and what their answer should settle, and
assign them (**Issues waiting on a person**).

A failure waits on a recurrence when its next occurrence is the only way left to
advance its diagnosis, repair or verification. Before concluding that, run copies on
its runner under the load it failed on, and force each ordering it could depend on
(`tests/AGENTS.md`, **Races**); where its evidence is too thin to diagnose, merge what
would capture it first. The maintainer counts such a failure as handled, and an open
issue for it tells the maintainer and the next session that work remains when none
does. Close its cause issue, or record the failure in the report's diagnosis
without filing one, saying what you tried and what its next failure should show; this
holds over **Retain engineering ownership** in `/tend-ci-runner:fix-a-bug`. The next
failed run brings it back to triage. An issue that tracks several tests closes once
each is fixed, owned elsewhere or waiting on a recurrence.

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
(a skipped or deleted test has not passed). For a failure only `test-macos` shows,
**A red `ci` on main is live** says what shows the before and after. Pull requests
run only the later-tier tests they edit, so run the claimed ones yourself. The merge
also waits for the pull request's CI to reach a terminal result on the exact head; `monitor-ci`,
**Which heads to poll**, says which session does that waiting. A failure there outside
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

A scheduled run runs every test a push runs, so main's push and schedule `ci` reports
share most of their failures. When both need diagnosis, the push report owns each
failure a push run also shows. The schedule report's diagnosis covers what pushes
don't run, the `journeys` and `nightly` tests, `test-macos` and
`journey-claude-code`, and links the push
report's diagnosis and cause issues for the rest instead of rerunning or bisecting
those tests itself.

The scheduled run's `test-macos` job runs every tier on macOS and takes four to five
hours, so reproduce a failure only it shows by dispatching that test alone on its
runner (`tests/AGENTS.md`, **Races**). The same dispatch failing on a branch at the
fix's base, and passing every copy on the fix's branch in enough copies that the
base's failure rate would have failed three of them (54 where the base failed 1 of
18), is the evidence from before and after the fix. Where no dispatch reproduces the
failure, the failing scheduled run is the evidence from before, and the next one on
main, after the fix merges, the evidence from after. If that run still fails, its
report brings the failure back to triage.

The scheduled run's `journey-claude-code` job runs the claude-code agent journey,
which your sandbox can't run: tmux and Claude Code's messaging need Unix sockets the
sandbox refuses. Diagnose from the job's log and its `journey-claude-code-*` artifact,
which holds each step's screen, Claude Code's debug log and the page's log. The
failing run is the evidence from before a fix, and the next scheduled run on main the
evidence from after.

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
(`notes/TODO.md` says how it is kept), not a report awaiting triage. When one reaches
you, whether through triage or an unread notification, take no action, post
nothing, and acknowledge the notification.

## Issues waiting on a person

A person learns what waits on them from their list of assigned issues, as
`notes/TODO.md`, "Backlog", says of the maintainer. So whenever a run stops work on
an issue because its next step is one only a person can take, such as a decision, a
review or a go-ahead, it assigns them in the same run, whichever workflow brought it
to the issue; a later run unassigns them once they act. A comment that asks a person
something without assigning them is missing from their list.

## Nightly: issues waiting on a person

A pull request that answers an issue Tend assigned to a person sends Tend no event.
So each nightly run reads every open issue Tend assigned to a person against main.
Close each issue that a merged change has settled, with a comment naming the change:
a change the person wrote or merged answered its question, or any change removed its
cause. This authorizes the closing that `/tend-ci-runner:nightly`'s **Resolved
issues** leaves to the repository's instructions, cause issues included. Leave
`backlog` issues alone (**Leave backlog issues to the maintainer**).

## Nightly: model and harness releases

Keep Leaf's model defaults current and find upstream capabilities worth adopting.
Each nightly run, scan the
[Claude Platform release notes](https://platform.claude.com/docs/en/release-notes/overview),
[OpenAI API changelog](https://developers.openai.com/api/docs/changelog),
[Claude Code changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md),
[Codex releases](https://github.com/openai/codex/releases),
[Codex product changelog](https://developers.openai.com/codex/changelog/), and
[Pi releases](https://github.com/earendil-works/pi/releases).
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
Bump prospectively: check the exact id against the provider's current models
page, run whatever eval or journey for the affected role the session can reach
(including grading when a judge changes), and land the bump without waiting on a
check that needs a harness or login the session lacks; the role's own runs after
landing, such as `publish-site`'s hosted journey, validate it, and a failure there
comes back as a CI report. Record the old and new models, upstream sources, the
validation that ran and the validation left to those runs, and keep model pins the
same across arms in a Leaf comparison. Regenerate Tend workflows from its config
when Tend's default changes, and follow **Landing** for changes requiring the
control-plane owner's approval. If a material tradeoff prevents a bump, report what
remains to establish.

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

In the rolling survey, apply `AGENTS.md`'s "Regular maintenance" to each file
you review. Propose a removal that takes a feature away in an issue for the
maintainer; a consolidation or delegation that keeps behavior is an ordinary fix.

## Review-runs: benchmark costs that grow

Root `AGENTS.md`, **Responsiveness**, sets how fast each cost may grow with the page,
and the daily scheduled `ci` run's `bench` job measures those costs. Nothing passes or
fails on its readings (`tests/AGENTS.md`, **Results do not depend on execution
speed**), because a CI runner's speed varies from run to run and no single threshold
separates a regression from a slow runner. So this review weighs the readings in place
of a cutoff.

Read the report of the latest scheduled run (`gh run list -w ci -e schedule`). Its
`bench-report-*` artifact holds the browser, documents and server tables, each reading
by size with the exponent of its growth. Earlier runs' artifacts go back 30 days, and
`dev/bench/data.js` on the `gh-pages` branch holds each run's CPU and `shown` readings
at 64 sections.

Judge from several runs whether a cost grows with the page faster than that rule
allows, or rises across runs at the same size, by more than the runner's noise
explains. The table marks `!` beside each exponent above its reading's `limit`.
The header of `dev/leaf_dev/commands/bench.py` says which readings a busy runner
stretches; an exponent compares sizes within one run, so a slow runner moves it less
than the readings themselves. Where a cost grows, open an issue that names the reading, its
values at each size, the runs compared, and the commits between the last run that read
it at its earlier level and the first that read it higher. Where an open issue already
tracks that cost, add only what it lacks, and leave one labelled `backlog` alone
(**Leave backlog issues to the maintainer**). Say in the run summary which runs you
compared, whether or not anything grew.

## Weekly: test tier budgets

Read the latest daily `ci` run that finished (`gh run list -w ci -e schedule`): its
`test` job's summary lists the tests over their directory's budget (`leaf-dev
suite profile`). A test over budget in two daily runs either moves to
`tests/journeys/` or gets faster. A single reading moves nothing, since one run's time
includes contention. Open one pull request with the moves, listing each test and the
times behind it.

## Weekly: interface sweep

Run `/ui-sweep` before dependency maintenance, following its **Reconcile** route:
a reproduced defect becomes a tested repair, and a design judgment stays in the
run report.

## Weekly: duplicate implementations

Sweep one area for capabilities implemented more than once, taking the area by ISO
week number (`date +%V`) modulo 4: 0, the JavaScript under `browser/`; 1, `packages/`
and the CSS under `browser/`; 2, `src/leaf/` and `hooks/`; 3, `dev/`, `build/`,
`tests/` and `worker/`. Copies seldom share a name or a directory, so list the
questions the area's helpers, constants, selectors, style rules and inline checks
answer, and search the whole tree for other answers to each, as `AGENTS.md`'s **What
it repeats** says. Consolidate each set into one home with every caller moved, in one
pull request for the area; leave a set another open pull request is
changing to a later sweep. In the description, name each copy's introducing pull
request (`git log -S`), so the copies added since the area's last sweep show what
review let through.

## Weekly: eval cases' frozen deliveries

An eval case that embeds a delivery envelope froze its `handling` clauses when it was
made, so a later change to the clauses under `$events` in
`browser/runtime/kernel-registry.json` leaves it scoring text no agent now receives.
Compare each case's embedded clauses with the registry's, and regenerate each stale
envelope from the current Leaf the way its header says it was made, keeping the case's
other facts. Leave a case whose header says it holds a wording on purpose, such as one
that pastes each arm's wording into its prompt. Run each regenerated case on head
(`uv run leaf-dev eval run <case> --harness claude-code --repeat 3`) and record the
commit and result in its header, as earlier re-freezes did. Open one pull request for
the week's cases, naming any whose result fell: the shipped handling regressed there,
or the case's criterion needs revisiting.

## Weekly: dependencies

Dependency automation rebuilds committed browser bundles on Dependabot's PR.
Read each `*.LICENSES.txt` diff: a package listed at two versions means the bump
split a closure (Shiki's packages pin each other exactly);
`pnpm update <package> --no-save` moves a locked dependency within its dependant's
range. Drop a Lit bump the Web Awesome build refuses. Bump `esbuild` by hand when a
bundle needs it, and rebuild everything.

Dependabot reports a failed update job only in the run list, so check each
ecosystem's job each week: `gh run list --event dynamic` names them
`<ecosystem> in /. - Update`, one each for `npm_and_yarn`, `uv` and
`github_actions`. When an ecosystem's newest job failed, fix the cause its log
names. When one ran none in the past week, start a run by merging a pull request
that edits `.github/dependabot.yml`: any change to that file starts every
ecosystem's update run. If that starts none either, assign the maintainer, since
only an admin can see whether Dependabot is paused.
