---
name: running-tend
description: Project-specific instructions loaded by tend workflows alongside AGENTS.md.
---

# Running tend — leaf

## Landing

Tend uses `merge: yolo`. Merge a pull request that fixes tests, without waiting
for maintainer approval, once each test it claims to fix failed before the change
and passes after it (a skipped or deleted test has not passed), and `monitor-ci`'s
poll exits 0 on the exact head. Pull requests run only the nightly tests they edit,
so run the claimed ones yourself.

Merge a fix that is correct but incomplete, and open an issue for what it leaves.
Changes to workflows, Tend's configuration, CODEOWNERS, or agent instructions
require the control-plane owner's fresh approval.

Merging squashes with `PR_TITLE` / `PR_BODY`, so the description becomes `main`'s
commit message; hold its claims to the standard the diff is held to.

## Review threshold

Apply `AGENTS.md`'s **Stage** and **Fix the underlying issue** sections to the
verdict. Once a change moves Leaf toward a coherent architecture and its claimed
path works, the review is done. Reserve findings for architectural seams,
cross-runtime invariants, public surface traps, regressions on the claimed path,
or a central claim or test that is false. Omit bounded edge cases, exhaustive
same-pattern cleanup, minor simplification, and prose or test polish unless they
expose one of those problems.

A diff that settles its symptom without reaching the underlying issue is an
architectural seam, not polish: name the issue, and withhold approval unless the
change meets the deferral condition in **Fix the underlying issue**.

## Review test selection

Before approving a product change, run the few tests that exercise the failures
the diff most plausibly introduces, chosen from the product paths and contracts
it touches rather than the test files it edits, and within the local limit in
`tests/AGENTS.md` ("Run the narrowest useful surface"): the complete `test` job
reports the rest once the change lands. A docs-only or generated-workflow change
may need none; a selected failure withholds approval.
Where a test itself is at issue, `tests/AGENTS.md` says which boundary it
belongs at. For a change that can alter browser startup, apply `AGENTS.md`'s
**Working on the repository** performance rule to the candidate and base
profiles from CI.

## Reading a red suite

Nearly every test drives a real browser, so a traceback can name a symptom
several boundaries after its cause. Two test-owned failures recur:

- **A read or press before the page said it was ready**, which a re-run hides.
  State the ordering (`tests/AGENTS.md`, **State races are arrangements, not
  probabilities** and **A state the page passes through is not a state to poll
  for**); don't repeat the gesture until it happens to hold.
- **A reading that has been widened before.** When the fix that presents itself
  is one more member of an accepted set, allowlist, or tolerance, read the line's
  history (`git log -L`); a set that keeps growing describes the suite's own
  noise, and the fix is against the test (`tests/AGENTS.md`, **A test cannot
  assert over noise it makes itself**).

## Fix every failure in a red run

Every failure in the run is the session's, including those earlier runs also hit;
a tracking issue records a failure but doesn't fix it. Open one pull request per
cause that no open pull request already covers.

## A red `ci` on main is live

Pull requests run the everyday and website-worker gates; main runs the complete
suite once, alongside its runtime, browser-framework and bundle gates. A red `ci`
on main affects whoever pulls next, so treat it as live. Main holds one complete-suite slot and a newer commit
replaces the one waiting, which GitHub records as a cancelled run whose `test`
job has no runner (`runner_id` 0); that is not a regression. A `test` that
held a runner and still ended cancelled hit its timeout, and that is a failure.

## Cloudflare logs

`CLOUDFLARE_API_TOKEN` is the `Leaf observability (Tend CI)` token in
`worker/README.md`: it reads the deployed site's Workers Observability logs and
Analytics Engine events and cannot deploy. It is set only for an agent answering
an issue or a red run on `main`. When an issue or a red `publish-site` concerns
the deployed site, diagnose from those records as the README describes. Drop the
token from any command that runs a pull request's code with
`env -u CLOUDFLARE_API_TOKEN`.

## Filing issues in other repos

Standing exception granted: file directly in agent-equipped targets (per
**Filing issues** in the bundled `/tend-ci-runner:act-in-other-repos` skill)
without asking permission here first. The default rule (open an issue here asking
permission first) still applies when the target shows no agent signals.

## Leave outage trackers for the drain

Leave a **"Bot temporarily unavailable"** tracker open until `tend-review-runs`
drains its rows, whatever its body says, since each row names a stranded
trigger. This applies by title; `ci-fix`
diagnosis trackers have no rows and `ci-fix` closes them.

## Nightly: agent release notes

Find upstream changes worth acting on in Leaf. Each nightly run, scan the
[Claude Code changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md),
[Codex releases](https://github.com/openai/codex/releases), and
[Codex product changelog](https://developers.openai.com/codex/changelog/).
Read entries since the last successful `tend-nightly` run, with a day's overlap;
on the first run, read the past week. If a source cannot be read, report that in
the run summary rather than treating it as having no changes.

Open an issue only for a concrete, material opportunity or incompatibility in
Leaf's current code or agent workflow. Check the affected implementation and
upstream documentation before deciding. Hooks, waking agents, background work,
plugins, MCP, and permissions can affect Leaf's host integration; a release
mentioning one of them does not by itself justify an issue. Claude Code's
`asyncWake` is the calibration example: a host capability that could improve
Leaf's comment-to-agent wake loop warrants investigation. Routine fixes,
cosmetic changes, and speculative relevance do not.

Expect a qualifying finding on roughly 5% of days. This is a high relevance
threshold, not a quota or a reason to suppress an important finding. Most runs
should open no release-note issue. Search open and closed issues and pull
requests before filing, and skip changes already covered, adopted, or declined.

For a qualifying finding, open an issue here, rather than implementing it as
part of the scan. Include the upstream version/date and source link, the
affected Leaf code or workflow, the concrete benefit or breakage, and a proposed
next step. Distinguish confirmed behavior from an integration hypothesis. When
nothing qualifies, keep the result in the run summary; do not post a digest.

## Weekly: interface sweep

Run `/ui-sweep` before dependency maintenance, following its **Reconcile** route:
a reproduced defect becomes a tested repair, and a design judgment stays in the
run report.

## Weekly: vendored browser dependencies

Dependabot's weekly grouped PR moves the root `package.json` and
`package-lock.json` but not the committed bundles built from them, so its
`check:browser` and vendored-bundle steps stay red until the output is rebuilt.
On that PR's branch:

```bash
npm ci
npm run build:browser
uv run build/vendor.py
```

Commit the result to the same branch. Read each `*.LICENSES.txt` diff: a package
listed at two versions means the bump split a closure (Shiki's packages pin each
other exactly); `npm update <package>` moves a locked dependency within its dependant's
range. Drop a Lit bump the Web Awesome build refuses. `esbuild` is left to move
by hand when a bundle needs it; bump it and rebuild everything.
