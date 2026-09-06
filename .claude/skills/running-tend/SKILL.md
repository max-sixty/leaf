---
name: running-tend
description: Project-specific guidance loaded by tend workflows alongside CLAUDE.md.
---

# Running tend — leaf

## Landing

Work from Tend lands as a pull request that a maintainer merges. The bot has
write access, and the `Merge access` ruleset holds merging to admins.

## Review threshold

Apply `CLAUDE.md`'s **Stage** section to the verdict. Once a change moves Leaf
toward a coherent architecture and its claimed path works, the review is done.
Reserve findings for architectural seams, cross-runtime invariants, public
surface traps, regressions on the claimed path, or a central claim or test that
is false. Omit bounded edge cases, exhaustive same-pattern cleanup, minor
simplification, and prose or test polish unless they expose one of those
problems.

## Filing issues in other repos

Standing exception granted: file directly in agent-equipped targets (per
**Filing Issues in Other Repos** in the bundled `running-in-ci` skill) without
asking permission here first. The default rule (open an issue here asking
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

Pull requests run the everyday suite before merge, while `wt merge` runs that
gate on the maintainer's machine. The complete nightly suite first runs after
main moves on either path, so a red `ci` on main is already affecting whoever
pulls next. Treat it as live.

## Reading a red suite

Nearly every test drives a real browser, so a red run has more ways to be
uninteresting here than in a repo of unit tests. Classify before writing a fix —
but not by whether the failures move between runs. `main` reddens on a different
test most days, and each of those failures reproduced on its own commit, most of
them deterministically, so movement across runs says nothing about which class
you have. Sort on what the failure is.

- **A read or press that ran before the page said it was ready.** The dominant
  class here, and the one a re-run hides. The test measures a point, presses it,
  or asserts on it while the page is still arriving at the state the gesture
  needs — a panel still widening the document, a scroll still settling, a
  response landed but not yet reconciled. It surfaces at a wait far from the
  read that caused it, so the traceback names the symptom rather than the cause.
  `tests/CLAUDE.md` already owns the fix under **State races are arrangements,
  not probabilities** and **A state the page passes through is not a state to
  poll for**: state the ordering, do not repeat the gesture until it happens to
  hold.
- **A reading that has been widened before.** The failure is a case some
  accepted set, allowlist, or tolerance does not cover, and the fix that presents
  itself is one more member. Read the line's history first (`git log -L`). A set
  that has already grown is describing the noise the suite makes rather than the
  behaviour the test names, so the next wording reddens main again.
  `tests/CLAUDE.md` owns the fix under **A test cannot assert over noise it makes
  itself**. The PR is against the test.
- **A real regression.** Deterministic, repeats at the same assertion across
  runs, and usually clusters on one widget or one behaviour. This is worth a fix
  PR.

## Weekly: interface sweep

Run `/ui-sweep` before dependency maintenance. This is the discovery pass for visual
and interaction behavior the suite has no stated invariant for yet. Follow its
**Fix and pin** route: a reproduced defect becomes a tested repair, while a design
judgment stays in the run report.

## Weekly: vendored browser dependencies

`.github/dependabot.yml` watches the action refs and `uv.lock`. It cannot watch
the browser dependencies, whose versions live in `scripts/vendor.py`'s PINS
table rather than a manifest. They drift silently, and this is the step that
catches it.

```bash
scripts/vendor.py --pins
```

Each row is a package, its pin, the bundle to rebuild if it has moved, and the
newest release that pin could take where that differs. `elkjs` and `entities` are
beautiful-mermaid's imports rather than Leaf's own choices, so their rows read
against the range it declares: a release outside it is not a pin to take, because
npm would install the declared version nested and the bundle would carry that one.
`esbuild` is the tool the three builds share rather than payload, so it moves when
a bundle needs it rather than on every release.

On drift, bump the entry in PINS and run `scripts/vendor.py <bundle>` — the
rebuilt bundle is the commit, not the version string on its own. A copy's output tracks its version directly.
`highlight` and `pierre` also read the language list out of the registry's
`$languages.names`, so their output is a function of both the pin and the
registry: rerunning them after an unrelated registry change is how the bundle
and the lint stay unable to disagree. Pierre and Shiki must move together when
their compatibility requires it.

Run the suite afterwards. The browser tests load the bundles, so a bad rebuild
surfaces there rather than in review.
