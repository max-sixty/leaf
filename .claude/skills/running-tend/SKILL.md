---
name: running-tend
description: Project-specific guidance loaded by tend workflows alongside CLAUDE.md.
---

# Running tend — leaf

## Landing

`CLAUDE.md` says landing is `wt merge`, a direct squash merge, never a PR. That
is written for a session at a workstation. Work from here lands as a pull
request that a maintainer merges — the bot has write access, and the `Merge
access` ruleset holds merging to admins.

## Filing issues in other repos

Standing exception granted: file directly in agent-equipped targets (per
**Filing Issues in Other Repos** in the bundled `running-in-ci` skill) without
asking permission here first. The default rule (open an issue here asking
permission first) still applies when the target shows no agent signals.

## Leave outage trackers for the drain

Leave the **"Bot temporarily unavailable"** tracker open until
`tend-review-runs` drains its rows; the outage ending is not enough because each
row names a stranded trigger. The tracker's own body invites the opposite —
"Close it once the outage is resolved" — but that line is boilerplate from the
automatic report, written without knowledge of the rows. Don't take it. A
comment can record recovery, but the drain owns the close. This applies by
title, not by the `tend-outage` label: `ci-fix` diagnosis trackers have no rows
and are closed by `ci-fix` itself.

## A red `ci` on main is the first signal, not the second

Nothing lands here through a pull request, so no CI run ever gates a change
before it is on main — `wt merge`'s local hooks are the only gate, and they run
on the maintainer's machine. That makes `ci-fix` the primary safety net rather
than a backstop, and it means a red `ci` on main is already affecting whoever
pulls next. Treat it as live.

## Reading a red suite

Nearly every test drives a real browser, so a red run has more ways to be
uninteresting here than in a repo of unit tests. Classify before writing a fix:

- **Contention.** Concurrent suites starve each other, and the failures surface
  as `Page.goto` timeouts and slow-read assertion failures scattered across
  unrelated tests — a shape that reads as "the browser layer is broken" when it
  means "the machine was busy". A run whose failures move between runs is this.
  Re-run before diagnosing.
- **A real regression.** Deterministic, repeats at the same assertion across
  runs, and usually clusters on one widget or one behaviour. This is worth a fix
  PR.
- **The network.** Tests marked `nightly` shell out to `bin/leaf` on the paths
  that resolve Playwright outside the script's lock, so they need pypi. CI
  passes `--run-nightly` deliberately (it holds a network). If only those tests
  fail while the rest of the suite is green, suspect the index rather than the
  code.

`scripts/linux-suite.sh` exists to reproduce a Linux-only failure from a Mac.
From CI you are already on Linux, so run the suite directly — the container adds
nothing here.

## Don't green a run by weakening what it proves

`tests/CLAUDE.md` opens by saying most of its norms were learned from a test that
passed while proving nothing, and every shortcut to a green run recreates one:
an `xfail` or `skip` added to a failing test, an `expect(...)` relaxed to a bare
`count()` or `is_hidden()`, a gesture swapped from real mouse input to
`dispatchEvent`. Each removes the safety net while looking like a fix. If a fix
reaches for one, the question to answer instead is what behaviour actually broke.

## Weekly: the two vendored bundles

`.github/dependabot.yml` watches the action refs and `uv.lock`. It cannot watch
the bundles under `plugins/leaf/skills/leaf/assets/vendor/`, because neither is
resolved from a manifest — each is produced by a script holding the version as a
shell variable. So they drift silently, and this is the step that catches it.

Read the pinned version out of each script and compare it against upstream:

```bash
grep HLJS_VERSION scripts/vendor-highlight.sh    # against: npm view highlight.js version
grep MARKED_VERSION scripts/vendor-marked.sh     # against: npm view marked version
```

On drift, bump the variable and rerun that script — the rebuilt bundle is the
commit, not the version string on its own. `vendor-marked.sh` copies upstream's
single ESM file, so its output tracks the version directly.
`vendor-highlight.sh` is a real build, and it reads the language list out of the
registry's `$languages.names`, so its output is a function of both the pin and
the registry: rerunning it after an unrelated registry change is how the bundle
and the lint stay unable to disagree.

Run the suite afterwards. The browser tests load both bundles, so a bad rebuild
surfaces there rather than in review.
