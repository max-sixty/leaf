---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, then resolve
`<root>/bin/leaf` to an absolute path. Run that launcher with `--root` and
continue only when it prints the same repository root. Use the absolute launcher
throughout; a bare `leaf` may resolve to the installed plugin instead.

Read `references/glossary.md` before naming or revising user-facing elements,
interaction contexts, navigation, chrome, view state, or an identifier governed by
those concepts. It is Leaf's canonical implementation vocabulary.

## Read the owning contract

Read the scoped `AGENTS.md` for every area the change reaches and the header of
each module changed. For a contract shared across modules or runtimes, read the
sidecar beside the Python code that owns the boundary;
`<root>/skills/leaf/scripts/AGENTS.md` lists them under "Protocol references".

This skill is maintainer workflow, not a home for product specifications. Agents
using Leaf read `<root>/skills/leaf/SKILL.md`; package authors read
`<root>/skills/leaf/references/packages.md`.

## Leave old state out of the handoff

Leaf owes nothing to state an earlier version wrote (`AGENTS.md`, "Stage"). A
handoff doesn't say that an existing page, log, or claim predates the change or
needs re-vendoring, and doesn't list reviving it as follow-up work.

## Explore an open design

When a new interface leaves a material visual or interaction choice unsettled,
first look in the shipped examples and `notes/` for an exploration of the same
surface, and extend its playground when it owns the same decision. Otherwise
initialize a page with the `playground` package and follow
`<root>/skills/leaf/packages/playground/guidance/author.md`: several coherent
options as named presets, each built far enough that the user can operate it in
the shared preview. The user's submitted configuration or feedback chooses the
one implementation the change keeps.

When the subject already exists, implement each candidate in the runtime and
theme that own the surface and present it through a shipped example or fixture.
When the user asks for sketches without implementation, keep the current surface
as the baseline, derive each sketch from its actual controls, copy, and styling,
and embed the operable current surface with a live `lf-specimen`
(`skills/leaf/references/page-authoring.md`).

## Prove and hand off a visible change

Review at a representative desktop viewport (`skills/leaf/assets/AGENTS.md`,
"Layout and motion"), and capture the viewport when fixed chrome should
appear. A Playwright screenshot of an element taller than the viewport draws
fixed overlays in the wrong place; crop a viewport capture instead.

Re-vendor before trusting a browser result after a runtime, theme, registry, or
widget change. A green suite does not judge visual quality; run `/ui-sweep` or
look at a composed page.

Compare against a baseline from `git merge-base HEAD main` ("Compare checkout
versions" below). For every difference a still can show, the handoff carries one
sentence and matched before/after screenshots, embedded in the reply or as one
`lf-shot`; a live preview may accompany the pair but does not replace it. For an
interaction-only change, keep both previews live and hand off the labeled URL
pair with the action that reveals the difference.

Before calling a served page or visible runtime change finished, open the exact
candidate URL, exercise the same journey in baseline and candidate (fragment,
viewport, theme, interaction state), and check both consoles. A live preview
handed to the user carries the fragment of the semantic block it is about (a
titled section's own id) and stays running.

## Preview a shipped example

`scripts/preview.py <example> --export` writes one file that opens offline.
`scripts/preview.py <example>` serves a live page at `.tmp/previews/<example>`
in the foreground, like a dev server: run it as a long-running command
(`run_in_background` in Claude Code), read its URL from the output, and stop it
when done. It follows source and runtime edits at one URL; each start rebuilds
the page from the fixture, and `--slot <name>` runs another copy.

A plain preview takes no task claim, so its presses reach only the page's log;
use it for screenshots and browser checks. `--user` claims the page at
`.tmp/previews/<example>-user` so the user's comments reach `leaf wait`, which
also makes every click this session drives there read as an unanswered user
move. So drive only claimless previews, start any `--user` preview from the
session the user talks to, and answer the user's feedback before restarting
their preview, since a restart discards the claim and the moves it held. Don't
idle a preview to quiet the loop; `idle` closes the page in the browser.

### In Codex

1. Start the preview with `--user` as a long-running command. A restarted
   preview is a new page and needs step 3 again.
2. Call `mcp__codex_app__open_in_codex` with the fragment URL as a browser
   target and `placement: "right"`.
3. Run `<root>/bin/leaf codex start <root>/.tmp/previews/<example>-user` so Leaf
   comments return to the current task.
4. Tell the user to select page text or use Leaf's comment affordance for a Leaf
   thread. Codex Annotation mode sends visual comments with their next chat
   message; the review pane is for feedback on a source line.

## Test the hosted website agent

`uv run <root>/scripts/verify_site.py local` builds the site, starts the website
adapter against the host's Codex login, asks for one heading edit, and verifies
the publication, reply, and changed page in Chrome. It bypasses the Cloudflare
Worker, container limits, and credential proxy. When a change touches those and
`OPENAI_API_KEY` is exported, run the same check through Wrangler's local
container:

```bash
npm ci --prefix <root>/worker
npm run build --prefix <root>/worker
<root>/scripts/verify-site-local.sh --agent
```

Neither loop proves edge rollout or production latency; the `publish-site`
workflow's run against the deployed release is the production reading.

## Compare checkout versions

Build the baseline in a detached worktree at the merge base:

```bash
candidate_root=$(git rev-parse --show-toplevel)
baseline_commit=$(git merge-base HEAD main)
baseline_parent=$(mktemp -d "${TMPDIR:-/tmp}/leaf-baseline.XXXXXX")
baseline_parent=$(cd "$baseline_parent" && pwd -P)
baseline_root="$baseline_parent/checkout"
git worktree add --detach "$baseline_root" "$baseline_commit"
```

Choose sources that isolate the change: one shared source for a runtime change,
or each checkout's copy when the authored content changed. Run the two previews
as separate long-running commands, adding `--user` to both when their URLs go to
the user:

```bash
"$candidate_root/scripts/preview.py" --source <baseline-source.html> \
  --runtime "$baseline_root" \
  --slot <slot>-baseline
```

```bash
"$candidate_root/scripts/preview.py" --source <candidate-source.html> \
  --runtime "$candidate_root" \
  --slot <slot>-candidate
```

After stopping both, remove the baseline:

```bash
git worktree remove "$baseline_root"
rmdir "$baseline_parent"
```

## Author or revise a page

Read `<root>/skills/leaf/SKILL.md` completely and follow its authoring,
validation, handoff, and conversation-loop routes, using the checkout launcher
for every `leaf` command and resolving its references from `<root>/skills/leaf/`.
To make an existing page exercise the current checkout, re-vendor it with the
checkout launcher (`<root>/skills/leaf/references/serving-pages.md`); fix or
report a compatibility refusal rather than falling back to the installed plugin.
A page that explains how a Leaf interface behaves lets the user operate it
(`references/specimen-explainers.md`).

## Refresh the public catalog stills

When a change adds or removes a worked example or changes its first viewport,
run `wt refresh-previews` from the repository root on macOS once the examples
are ready, and again after integrating `main` or any later fix that changes a
first viewport. It pushes the stills to `max-sixty/leaf-assets` and updates
`example-previews.json`; that push is part of the authorized change. Run
`wt setup` first in a new checkout; if Worktrunk asks to approve the project
commands, ask the user to run `wt config approvals add`.

## Land a change

A branch may land with a red gate only
when every failure also fails on the exact merge-base SHA under the same CI job
and selection; until it reproduces there, it is the branch's. Use the base SHA's
GitHub Actions run as the control, not a local container or a green run a few
commits back. Main holds one nightly slot, so a base commit may carry no nightly
result; push that SHA as a branch and dispatch `ci` on it. A case can differ
between Linux and a Mac, or between the full suite under `-n 2` and a run alone.

`wt merge --no-hooks` lands past a red local hook whose failures reproduce on the
base, and reuses a passing result when a newer `main` dislodges the merge. Finish
either with `git push origin main:main`, since the skipped hook normally pushes. `✗ Can't push to local main branch` is a
fast-forward failure.

Installed sessions load host caches, not the checkout. Claude Code picks up a
push on its marketplace sweep; the post-merge hook refreshes an installed Codex
plugin, and after a merge that skipped hooks, run
`codex plugin marketplace upgrade leaf`.
