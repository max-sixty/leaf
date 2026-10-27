# Grind: shared rules

You are one of many agents working Leaf's backlog issues in parallel while the
maintainer (Max, GitHub `max-sixty`) is away. Nobody will answer a question before
you finish, so don't ask one: where a choice stalls you, take the option you would
defend, and say in your PR and report that it's a call Max may reverse. Your item's
paragraph says what to do; these rules say how.

## Start

- Your cwd is an isolated git worktree branched from `main`. Run `git fetch -q origin`, then
  `git merge -q --ff-only origin/main`, so you start from current main.
- Run `uv run --frozen leaf-dev setup` in the foreground before any test: a fresh
  worktree may not have finished (or started) its background install, and without it
  `node_modules` and the browser bundles are missing.
- Your Bash calls run under a worktree-isolation guard that refuses compound
  commands it can't verify (pipelines with computed names, `cd x && …`, `-C` to
  another dir). Run one plain command per call, or put a compound sequence in a
  script under `.tmp/` (written with the Write tool) and run it as `bash .tmp/x.sh`.
- Load the skills `developing-leaf` (required), `developing-code`, and, as they
  apply, `writing-tests`, `developing-python`, `writing-prose` (for the commit and PR
  text). Read the root `AGENTS.md` and the `AGENTS.md` of every area you change before
  changing it.
- Check that the item is still live on current main before building anything. If it
  is already fixed, or the brief's premise is false, stop and report that; it is a
  useful result.

## Work

- Fix the cause at the layer that owns it (root `AGENTS.md`, "Fix the underlying
  issue"). A patch that leaves the code harder to maintain doesn't go in.
- Get a reproducer before fixing a bug, and show it failing before and passing after.
  For a performance item, measure before and after on the same machine state and
  report both numbers with the command that produced them.
- Write or adjust a test that protects the behavior a user depends on, at the
  boundary that owns it (`tests/AGENTS.md`).
- Do not spawn subagents or run workflows.
- Stop only processes you started, by their pid. Never `pkill -f` a pattern: other
  sessions run previews and servers from the same commands.
- Never use `git stash`: its stack is shared with every worktree and other sessions.
  To compare against base, commit WIP and `git checkout <base> -- <paths>`, then
  restore from your commit.
- Touch only your own worktree. Never run git against another worktree or the main
  checkout.

## The machine is shared

The other agents and Max's own sessions share this Mac (18 cores).

- Choose a `-k` selection from what your change can affect, not from your new
  test's name: grep `tests/` for the selectors, attributes, widget names and
  viewport widths you changed, and include every test that reads them. A narrow
  `-k` has let red tests through review before. Confirm the selection actually
  ran the tests you meant (the count in pytest's summary).
- Run only the tests that cover what you change: named test files or `-k` selections,
  plus `pnpm run test:runtime` when you touch `browser/runtime` and `pnpm run check`
  when you touch `browser/types/`, `browser/runtime/framework/`, `worker/src/`, or
  the bundle lock. Never run
  `uv run pytest tests`, a whole browser test directory, `--run-main`,
  `--run-nightly`, `tests/browser` or `tests/journeys` as a whole.
- Before a browser test run or probe batch, read `sysctl -n vm.loadavg`. If the
  one-minute load is above 36, wait a minute and check again (at most 10 minutes),
  then run anyway with `-n 2` or less. Don't use `taskpolicy -b` for browser tests:
  it throttles headless Chrome to about 10 fps and breaks timing.
- Don't run `leaf-dev journey`, `leaf-dev eval` or CI dispatches unless your brief
  says to.
- Format with the pre-commit hooks (`uv run pre-commit run --files <files>`), not a
  bare `ruff` or `npx prettier`.

## Land your work as a draft PR

- Commit with a message in Leaf's style: an imperative title saying what the user or
  maintainer gains, a body giving the mechanism and the evidence, and your own
  model's `Co-Authored-By:` trailer.
- Push with `git push -q origin HEAD:refs/heads/grind/<item-id>` (the brief gives the
  id; the `refs/heads/` prefix is needed from a detached HEAD).
- Open a **draft** PR: `gh pr create --draft --base main --head grind/<item-id>
--title "<title>" --body-file <file>`. The body becomes `main`'s squash commit
  message if it lands, so hold its claims to the diff's standard: what changed, why,
  the before/after evidence, what you ran, and what you didn't verify. Say
  `Closes #N` for the issue your item came from, or `Part of #N` if work on it
  remains. End it with the line
  `> _This was written by Claude Code on behalf of max-sixty_`.
- Don't mark it ready, merge it, request reviewers, or wait for CI.
- Never force-push or rewrite pushed history, even on your own branch: add commits.
- If a Leaf restriction (a CSP, a validator, an allowlist) blocks the item, don't
  work around it: stop and report what it blocks.

## Report

End your final message with a fenced `json` block, then at most a short paragraph:

```json
{
  "item": "<item-id>",
  "outcome": "pr | no-change | blocked | partial",
  "pr_url": "",
  "branch": "grind/<item-id>",
  "summary": "one sentence: what is true now",
  "evidence": "before/after numbers or the repro, with commands",
  "tests_run": ["…"],
  "unverified": ["what you could not check"],
  "decisions_taken": ["calls Max may reverse"],
  "friction": ["what in the repo, its instructions or tooling slowed you, and where"],
  "follow_ups": ["durable work this uncovered"]
}
```

`friction` feeds a study of the grinding process itself. Be specific: a missing
command, an instruction that sent you the wrong way, a slow test, a flaky probe, a
fact you had to rediscover.
