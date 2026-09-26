---
name: running-tend
description: Project-specific guidance loaded by tend workflows alongside AGENTS.md.
---

# Running tend — leaf

## Landing

Tend uses `merge: yolo`. Merge a pull request without waiting for maintainer
approval when it makes a modest change that fixes tests, the relevant CI checks
pass on the exact pull request head, and the claimed fix is verified by those
checks. This includes test-owned failures and small product fixes needed to make
the tests pass. Changes to workflows, Tend's configuration, CODEOWNERS, or agent
instructions require the control-plane owner's fresh approval.

Merging squashes, and the repository is set to `PR_TITLE` / `PR_BODY`, so a
description is `main`'s commit message for that change rather than review
scaffolding that the merge discards. Hold a claim in it to the standard the diff
is held to. Attribution is the claim that goes wrong: read which file an earlier
commit changed off that commit's own per-file diff — `git show <sha> -- <path>`,
or `--stat` for the shape — because a grep over a whole-directory diff prints
the matching lines without saying which file each came from.

## Review threshold

Apply `AGENTS.md`'s **Stage** and **Fix the underlying issue** sections to the
verdict. Once a change moves Leaf toward a coherent architecture and its claimed
path works, the review is done.
Reserve findings for architectural seams, cross-runtime invariants, public
surface traps, regressions on the claimed path, or a central claim or test that
is false. Omit bounded edge cases, exhaustive same-pattern cleanup, minor
simplification, and prose or test polish unless they expose one of those
problems.

A diff that settles its symptom without reaching the underlying issue is an
architectural seam, not polish: name the issue, and withhold approval unless the
change meets the deferral condition in **Fix the underlying issue**.

## Cloudflare logs

`CLOUDFLARE_API_TOKEN` in the agent's environment is the
`Leaf observability (Tend CI)` token in `worker/README.md`: it reads the
deployed site's Workers Observability logs and Analytics Engine events and
cannot deploy. It is set only for an agent answering an issue or a red run on
`main`, and empty everywhere else. When an issue or a red `publish-site`
concerns the deployed site, query its logs as that README describes and diagnose
from the records. Before running a pull request's code in a session that holds
the token, drop it from that command's environment with
`env -u CLOUDFLARE_API_TOKEN`.

## Filing issues in other repos

Standing exception granted: file directly in agent-equipped targets (per
**Filing issues** in the bundled `/tend-ci-runner:act-in-other-repos` skill)
without asking permission here first. The default rule (open an issue here asking
permission first) still applies when the target shows no agent signals.

## Leave outage trackers for the drain

Leave the **"Bot temporarily unavailable"** tracker open until
`tend-review-runs` drains its rows; the outage ending is not enough because each
row names a stranded trigger. The tracker's own body invites the opposite —
"Close it once the outage is resolved" — but that boilerplate does not account
for the rows. Ignore it. A comment can record recovery, but the drain owns the
close. This applies by title, not by the `tend-outage` label: `ci-fix` diagnosis
trackers have no rows and are closed by `ci-fix` itself.

## A red `ci` on main is live

Pull requests run the everyday and website-worker gates; main runs the everyday
gate and then, once it is green, the complete suite in the same run. A red `ci` on
main is already affecting whoever pulls next. Treat it as live.

Main runs one complete suite at a time, and a newer commit replaces the one waiting
for that turn. GitHub records a replaced entry as a cancelled run, which is the
common shape of a cancelled `ci` on main and not a regression: its `nightly` job
never started, so the job carries no runner (`runner_id` 0 and an empty
`runner_name`), there is nothing to fix, and the commit that took the turn reports
on its own run.

Read that field rather than the step count or the elapsed time, because a job that
exceeds its own `timeout-minutes` also concludes `cancelled`, with steps recorded
and a runner assigned. Elapsed time misleads from the other side as well: a job
that never started reports `started_at` equal to its `created_at`, so its span
measures the wait it sat through rather than any work it did. A `nightly` that held
a runner and still ended cancelled wedged for its full bound, and that is a failure
to read.

## Review test selection

Before approving a product change, choose and run the smallest test selection
that exercises the failures the diff could introduce. Select from the product
paths and contracts in the diff, not from the test files it happens to touch.
The review selection supplements the everyday CI gate. A docs-only or
generated-workflow change may need no additional test; a selected failure
withholds approval.

For a change that can alter browser startup, apply `AGENTS.md`'s **Working on the
repository** performance rule. Read the candidate profile from CI and compare it with
the base. If requests or bytes rise before presentation, check that the PR names the
user-visible benefit and why the work must happen then.

When a high-level browser test is slow or fails on timing or geometry outside its
contract, repair its arrangement or move that contract to the lower boundary that
can prove it. Keep a browser case only where it proves that the boundaries work
together.

## Reading a red suite

Nearly every test drives a real browser, so the traceback can name a symptom
several boundaries after its cause. Find the first violated contract, reproduce at
the lowest boundary that preserves the failure, then determine whether the product,
test, or execution environment owns it. Failure movement, determinism, and clustering
can guide that search; none decides who owns the fix.

Two test-owned failures recur here:

- **A read or press that ran before the page said it was ready.** The dominant
  class here, and the one a re-run hides. The test measures a point, presses it,
  or asserts on it while the page is still arriving at the state the gesture
  needs — a panel still widening the document, a scroll still settling, a
  response landed but not yet reconciled. It surfaces at a wait far from the
  read that caused it, so the traceback names the symptom rather than the cause.
  `tests/AGENTS.md` already owns the fix under **State races are arrangements,
  not probabilities** and **A state the page passes through is not a state to
  poll for**: state the ordering, do not repeat the gesture until it happens to
  hold.
- **A reading that has been widened before.** The failure is a case some
  accepted set, allowlist, or tolerance does not cover, and the fix that presents
  itself is one more member. Read the line's history first (`git log -L`). A set
  that has already grown is describing the noise the suite makes rather than the
  behaviour the test names, so the next wording reddens main again.
  `tests/AGENTS.md` owns the fix under **A test cannot assert over noise it makes
  itself**. The PR is against the test.

## Weekly: interface sweep

Run `/ui-sweep` before dependency maintenance. This is the discovery pass for visual
and interaction behavior the suite has no stated invariant for yet. Follow its
**Reconcile** route: a reproduced defect becomes a tested repair, while a design
judgment stays in the run report.

## Weekly: vendored browser dependencies

`.github/dependabot.yml` watches the root `package.json`, which pins every
JavaScript package the committed browser output is built from: the page payload
the browser framework build bundles (Lit and Signals) and each package a
`scripts/vendor.py` bundle imports. It opens one grouped PR a week that moves
`package.json` and `package-lock.json` but not the output, so CI's
`check:browser` and vendored-bundle steps stay red on it until the output is
rebuilt. On that PR's branch:

```bash
npm ci
npm run build:browser
uv run scripts/vendor.py
```

Commit what that changes to the same branch; the rebuilt bundle is the change,
not the version string on its own. Read the diff of each `*.LICENSES.txt`: one
package listed at two versions means the bump split a closure, the likely case
being Shiki: its packages pin each other exactly, and the two Pierre depends on
(`shiki` and `@shikijs/transformers`) stay at their locked versions while the
ones Leaf imports move. `npm update <package>` moves a locked dependency within
its dependant's range; rerun the rebuild after it. Where the webawesome build
refuses a Lit outside Web Awesome's declared range, drop that bump from the PR.

`esbuild` is the tool the builds share rather than payload, so Dependabot leaves
it alone and it moves when a bundle needs it: bump it in `package.json` and
rebuild everything. `highlight` and `pierre` also read the language list out of
the registry's `$languages.names`, so their output is a function of both the
lock and the registry: rerunning them after an unrelated registry change is how
the bundle and the lint stay unable to disagree.

Run the suite afterwards. The browser tests load the bundles, so a bad rebuild
surfaces there rather than in review.
