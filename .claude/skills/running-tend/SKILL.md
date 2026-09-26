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

Merging squashes with `PR_TITLE` / `PR_BODY`, so the description becomes `main`'s
commit message; hold its claims to the standard the diff is held to. Attribute
a file's change from that commit's per-file diff (`git show <sha> -- <path>`),
not a grep over a whole-directory diff.

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

Before approving a product change, run the smallest test selection that exercises
the failures the diff could introduce, chosen from the product paths and
contracts it touches rather than the test files it edits. A docs-only or
generated-workflow change may need none; a selected failure withholds approval.
Where a test itself is at issue, `tests/AGENTS.md` says which boundary it
belongs at. For a change that can alter browser startup, apply `AGENTS.md`'s
**Working on the repository** performance rule to the candidate and base
profiles from CI.

## Reading a red suite

Nearly every test drives a real browser, so a traceback can name a symptom
several boundaries after its cause. Find the first violated contract, reproduce
at the lowest boundary that preserves it, then decide whether the product, the
test, or the environment owns it. Two test-owned failures recur:

- **A read or press before the page said it was ready**, which a re-run hides.
  State the ordering (`tests/AGENTS.md`, **State races are arrangements, not
  probabilities** and **A state the page passes through is not a state to poll
  for**); don't repeat the gesture until it happens to hold.
- **A reading that has been widened before.** When the fix that presents itself
  is one more member of an accepted set, allowlist, or tolerance, read the line's
  history (`git log -L`); a set that keeps growing describes the suite's own
  noise, and the fix is against the test (`tests/AGENTS.md`, **A test cannot
  assert over noise it makes itself**).

## A red `ci` on main is live

Pull requests run the everyday and website-worker gates; main runs the everyday
gate and then the complete suite. A red `ci` on main affects whoever pulls next,
so treat it as live. Main holds one complete-suite slot and a newer commit
replaces the one waiting, which GitHub records as a cancelled run whose `nightly`
job has no runner (`runner_id` 0); that is not a regression. A `nightly` that
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
trigger. A comment can record recovery. This applies by title; `ci-fix`
diagnosis trackers have no rows and `ci-fix` closes them.

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
uv run scripts/vendor.py
```

Commit the result to the same branch, then run the suite, since the browser tests
load the bundles. Read each `*.LICENSES.txt` diff: a package listed at two
versions means the bump split a closure (Shiki's packages pin each other
exactly); `npm update <package>` moves a locked dependency within its dependant's
range. Drop a Lit bump the Web Awesome build refuses. `esbuild` is left to move
by hand when a bundle needs it; bump it and rebuild everything.
