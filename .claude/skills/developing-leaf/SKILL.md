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

For a contract shared across modules or runtimes, read the sidecar beside the
Python code that owns the boundary;
`<root>/skills/leaf/scripts/AGENTS.md` lists them under "Protocol references".

To check what the code does, call it: the checkout's environment installs `leaf`
and `leaf_dev` editable, so `uv run python -c 'from leaf... import ...'` imports
either without a `sys.path` edit. A tag's schema is in the registry of the package
that ships it:

```bash
jq 'select(has("lf-shot"))."lf-shot"' \
  skills/leaf/assets/registry.json skills/leaf/packages/*/registry.json
```

## Leave old state out of the handoff

Leaf owes nothing to state an earlier version wrote (`AGENTS.md`, "Stage"). A
handoff doesn't say that an existing page, log, or claim predates the change or
needs re-vendoring, and doesn't list reviving it as follow-up work.

## Explore an open design

Whenever the user is to choose among designs for a visual or interaction
question, whether options for a new interface, alternatives to a shipped one, or
sketches they asked for, put the candidates in one playground, where the user
operates each, comments on it, and submits a choice. The submitted configuration
or feedback chooses the one implementation the change keeps. First look in the
shipped examples and `notes/` for an exploration of the same surface, and extend
its playground when it owns the same decision.

A playground is one HTML file, like a standalone sketch. Write it under `.tmp/`
and serve it with `uv run leaf-dev preview --source <file> --user` ("Preview a
page"), which builds the page from that file alone. Its CSS reads the live
theme's tokens, and the `playground` package's elements
(`<root>/skills/leaf/packages/playground/guidance/author.md`) wrap the
candidates: a `choice` control naming them, the candidates in its preview, and
an output saying what to build. Add presets and further controls only where the
user tunes more than the choice.

When the subject already exists and the candidates are to be implemented,
implement each in the runtime and theme that own the surface and present it
through a shipped example or fixture. A sketch without implementation is
page-local markup derived from the current surface's controls, copy, and
styling, shown beside that surface as the baseline, which a live `lf-sample`
(`skills/leaf/references/page-authoring.md`) embeds operable.

## Prove and hand off a visible change

Review at a representative desktop viewport (`skills/leaf/assets/AGENTS.md`,
"Layout and motion"), and capture the viewport when fixed chrome should
appear. A Playwright screenshot of an element taller than the viewport draws
fixed overlays in the wrong place; crop a viewport capture instead.

Re-vendor before trusting a browser result after a runtime, theme, registry, or
widget change. A green suite does not judge visual quality; run `/ui-sweep` or
look at a composed page.

To ask a page a question, such as where an element sits, what style it computes, or
what holds focus after a key, run `uv run leaf-dev probe` rather than writing a
Playwright script: it builds the page from this working tree, runs the input steps
you give it, and prints what a JavaScript expression returns, with `--base` for the
merge base beside it (`dev/AGENTS.md`).

Compare against the merge base with `main`. `uv run leaf-dev stills`
screenshots a catalogue of states on both runtimes and crops each one that
changed into a before/after pair; commit first, since it compares commits. The
catalogue holds states a user reaches by acting as well as pages at rest, because
a change can alter what only such a state draws: a padding moved for layout once
put a row over a focus ring drawn only while the element is focused. Where a
change reaches a state the catalogue lacks, add it to `STATES` instead of driving
the state by hand.

For every difference a still can show, the handoff carries one sentence and
matched before/after screenshots, embedded in the reply or as one `lf-shot`; a
live preview may accompany the pair but does not replace it. For an
interaction-only change, serve both versions ("Compare checkout versions" below),
keep both previews live, and hand off the labeled URL pair with the action that
reveals the difference. Exercise the same journey in both at the same fragment,
viewport, theme, and interaction state. A live preview handed to the user
carries the fragment of the semantic block it is about (a titled section's own
id) and stays running.

## Preview a page

`uv run leaf-dev preview <example> --export` writes one file that opens offline.
`uv run leaf-dev preview <example>` serves a live page at `.tmp/previews/<example>`
in the foreground, like a dev server, so run it as a long-running command
(`run_in_background` in Claude Code). `--source <file>` serves any authored HTML
file in place of a shipped example. It follows source and runtime edits at one
URL; each start rebuilds the page from the fixture, and `--slot <name>` runs another copy.

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

`uv run --project <root> leaf-dev verify-site local` builds the site, starts the
website adapter against the host's Codex login, asks for one heading edit, and
verifies the publication, reply, and changed page in Chrome. It bypasses the
Cloudflare Worker, container limits, and credential proxy. When a change touches
those and `OPENAI_API_KEY` is exported, run the same check through Wrangler's local
container:

```bash
npm ci --prefix <root>/worker
npm run build --prefix <root>/worker
uv run --project <root> leaf-dev verify-site wrangler --agent
```

The `publish-site` workflow's run against the deployed release is the only
production reading.

## Test a terminal Codex task

`uv run --project <root> leaf-dev verify-codex-task` runs a real Codex task, with
this working tree installed as its plugin, through the App Server adapter `leaf codex
start` leaves running, and checks each comment it posts is answered once and each
turn is closed under App Server's id. Run it after a change to `codex.py`,
`codex_adapter.py`, `hooks.py`, `hook_carrier.py`, or the claim's turn in
`service.py`; the suite scripts App Server, and only this run shows what Codex
itself sends. It spends a few turns on the host's Codex login, and CI has none.

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
uv run --project "$candidate_root" leaf-dev preview --source <baseline-source.html> \
  --runtime "$baseline_root" \
  --slot <slot>-baseline
```

```bash
uv run --project "$candidate_root" leaf-dev preview --source <candidate-source.html> \
  --runtime "$candidate_root" \
  --slot <slot>-candidate
```

## Author or revise a page

Every authored Leaf source is a page: a site page under `docs/`, a shipped
example or fixture, a playground, or a page made for this conversation. Before
writing its content, read `<root>/skills/leaf/SKILL.md` completely and follow
its authoring, validation, handoff, and conversation-loop routes, using the
checkout launcher for every `leaf` command and resolving its references from
`<root>/skills/leaf/`.
To make an existing page exercise the current checkout, re-vendor it with the
checkout launcher (`<root>/skills/leaf/references/serving-pages.md`); fix or
report a compatibility refusal rather than falling back to the installed plugin.
A page that explains how a Leaf interface behaves lets the user operate it
(`references/sample-explainers.md`).

## Score a guidance change

Each `evals/<case>/case.yaml` is a moment in a session that `claude plugin eval`
hands a headless Claude Code, with this checkout as its only plugin, so the child
loads `leaf:leaf` and reads the references as a real session does. Score a change to
`skills/leaf/` on the cases it bears on:

```bash
uv run leaf-dev guidance-eval [CASE]... [--base REF] [--runs N]
```

It runs the cases on the base's guidance (the merge base with `main` by
default) and the working tree's at once, and prints each case's passes per arm and the
cost. It passes `--allow-tools Skill Read`, without which the child's `dontAsk` mode denies
the skill and the references and every run answers with no guidance, while
`loads-leaf` still passes on the attempt. So every case also grades that the child
read the reference it tests, and a run that fails that check measured nothing.

Grow the suite slowly, toward a modest set of cases that each tell two wordings
apart. Measure with whatever scenarios and guardrails the change needs, then add a
case only if it pins a clause no existing case pins and it separated two arms you ran:
the base failed most runs and the change passed every run, or a blunter draft failed
a guardrail the change passes. That is usually one case per problem, and rarely more
than two. A case both arms passed goes in the commit message, not the suite. The
comment above `schema_version` says where the case came from and what it measured;
`description` names the clause it pins, and `tags` its area.

A prompt ends by asking for the HTML in the reply, since the child has no page
directory. It cannot search the plugin either, so it answers from the references
without the registry. The prompt never states the behavior under test. Grade a fixed
form with a `regex` grader, and a judgment with an `llm` grader whose `criteria`
state the passing reading without requiring particular wording.

Run cold, a case that states the situation plainly usually passes on both arms: the
failing session had its own earlier turns or a competing instruction pulling the
other way, so paste those into the prompt. A rule that loses only to a long
session's context needs a replay of that session instead.
`notes/usability-eval/harness.py` runs cases that need a page directory and `leaf`.
No grader has been checked against a person's judgment, so a pass is weak evidence.

## Refresh the public catalog stills

When a change adds or removes a worked example or changes its first viewport,
run `wt refresh-previews` from the repository root on macOS once the examples
are ready, and again after integrating `main` or any later fix that changes a
first viewport. It pushes the stills to `max-sixty/leaf-assets` and moves the pin
in `leaf-assets.json` and the README's image URLs; that push is part of the
authorized change. `uv run leaf-dev record-demo` does the same for the README's
recording and stills and the site's card. Run `wt setup` first in a new checkout;
if Worktrunk asks to approve the project commands, ask the user to run
`wt config approvals add`.

## Land a change

A red gate is the branch's to fix. A pull request's `test` job and the local
pre-merge `tests` run the broad selection, which main passes, plus the nightly-marked
tests in the test files the change touches. The rest of the nightly suite runs once
main moves, and `tend-ci-fix` answers it when it fails.
`wt merge` checks the rebased tree and lands it; `✗ Can't push to local main branch`
is a fast-forward failure.

Installed sessions load host caches, not the checkout. Claude Code picks up a
push on its marketplace sweep; the post-merge hook refreshes an installed Codex
plugin, and after a merge that skipped hooks, run
`codex plugin marketplace upgrade leaf`.
