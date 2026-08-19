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
