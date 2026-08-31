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

## The browser the suite needs is already here

`.config/tend.yaml`'s `sandbox_setup:` installs the Playwright headless shell
into this sandbox's own cache before the session starts, so `uv run pytest tests
--run-nightly` drives a real browser from here. Don't install it again, and
don't read a browser test as unrunnable — if a launch does fail, that is a fact
about the run worth reporting, not a step to work around. `playwright install
--with-deps` is the one that cannot work: it escalates, and the sandbox user has
no sudo.

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
- **A real regression.** Deterministic, repeats at the same assertion across
  runs, and usually clusters on one widget or one behaviour. This is worth a fix
  PR.
- **The catalog preview digest.**
  `test_site.py::test_the_public_catalog_is_a_visual_index_of_full_page_routes`
  failing on `preview inputs changed — rerun scripts/example-previews.py` is
  neither a race nor a regression, and it is the single most frequent red on
  main. `capture_input_files()` hashes every file under `examples/`,
  `skills/leaf/assets`, `skills/leaf/packages/default` and each package named in
  `examples/layer.json`, plus a short list of `docs/` and `scripts/` files — so
  any layer commit re-stales `docs/example-previews.json`. The assertion carries
  `pytest.mark.nightly` and `ci.yaml` passes `--run-nightly` only on `push`, so
  it first speaks on main, after the merge, and a capture is current only on a
  commit where it was the last layer change to land — which a pull request
  cannot arrange. #133 measured all of that; don't re-derive it.

  What a session can still add is which half went stale. Recapture at the last
  tree whose manifest matched its own inputs and at the tip, both on this
  runner, and compare the stills byte for byte. Identical means the refresh is
  hash-only and can be made from here; changed means the gallery genuinely moved
  and only the authoring machine can take it, because the runner carries none of
  the faces `theme.css` asks `--serif` for first and re-sets the prose in a
  substitute. Whether the gate should keep hashing every runtime file is a
  maintainer's design call, last argued on #133 — which is closed, so nothing
  tracks it now.
- **Contention.** Concurrent suites starve each other, and the failures surface
  as `Page.goto` timeouts and slow-read assertion failures scattered across
  unrelated tests — a shape that reads as "the browser layer is broken" when it
  means "the machine was busy". Confirm it from the run rather than from the
  spread: unrelated tests failing on waits none of them owns, and every job on
  the commit slow against its usual wall time. It is the rarest of the five.
- **The network.** Tests marked `nightly` shell out to `bin/leaf`, which resolves
  everything it needs — Playwright included — through the host's index. CI passes
  `--run-nightly` deliberately (it holds a network). If only those tests fail
  while the rest of the suite is green, suspect the index rather than the code.

Reproducing at `-n0` keeps the evidence, but it classifies in one direction
only: a failure that reproduces is real, while one that does not is still
unclassified — `-n0` also drops the load some races need, so repeat it to
measure a rate before falling through to contention. A re-run discards the
evidence instead: the second attempt replaces the run's reported conclusion
while both stay separately true, so a diagnosis written against attempt 1 does
not describe attempt 2. If you re-run anyway, cite the attempt you read.

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

## Weekly: vendored browser dependencies

`.github/dependabot.yml` watches the action refs and `uv.lock`. It cannot watch
the browser dependencies, whose versions live in `scripts/vendor.py`'s PINS
table rather than a manifest. They drift silently, and this is the step that
catches it.

```bash
scripts/vendor.py --pins
```

Each row is a package, its pin, the bundle to rebuild if it has moved, and
upstream's latest where that differs. `esbuild` is the tool the three builds
share rather than payload, so it moves when a bundle needs it rather than on
every release.

On drift, bump the entry in PINS and run `scripts/vendor.py <bundle>` — the
rebuilt bundle is the commit, not the version string on its own. A copy's output tracks its version directly.
`highlight` and `pierre` also read the language list out of the registry's
`$languages.names`, so their output is a function of both the pin and the
registry: rerunning them after an unrelated registry change is how the bundle
and the lint stay unable to disagree. Pierre and Shiki must move together when
their compatibility requires it.

Run the suite afterwards. The browser tests load the bundles, so a bad rebuild
surfaces there rather than in review.
