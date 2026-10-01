---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, check that
`<root>/bin/leaf --root` prints that root, and run every `leaf` command through that
absolute launcher; a bare `leaf` may run the installed plugin instead.

Read `references/glossary.md` before naming or revising a user-facing element,
interaction, navigation, chrome, view state, or an identifier for one of them. It is
Leaf's canonical implementation vocabulary.

## Read the owning contract

A contract shared across modules or runtimes lives in the sidecar beside the Python
code that owns the boundary; `<root>/skills/leaf/scripts/AGENTS.md` lists them under
"Protocol references". To check what the code does, call it: `leaf` and `leaf_dev` are
installed editable, so `uv run python -c 'from leaf... import ...'` needs no
`sys.path` edit. A tag's schema is in the registry of the package that ships it:

```bash
jq 'select(has("lf-shot"))."lf-shot"' \
  skills/leaf/assets/registry.json skills/leaf/packages/*/registry.json
```

## Leave taste to the authoring agent

Code enforces only what Leaf needs to work: a contract between modules, or a guarantee
the user relies on, such as a gesture being recorded or nothing moving under the
pointer. Taste goes in the shipped guidance as a goal and its reason, so the authoring
agent weighs it against its own page. A CSS rule, validator, or Layout that fixes how
many tiles share a row overrides every page that needs another number. A check may
report what it sees, as the render check names where a tile row wraps, and leave the
call to the agent.

## Explore an open design

When the user is to choose among designs for a visual or interaction question, put the
candidates in one playground, where the user operates each, comments, and submits a
choice; the submission picks the one implementation the change keeps. First look in
the shipped examples and `notes/` for a playground that owns the same decision, and
extend it.

A playground is one HTML file under `.tmp/`, served with
`uv run leaf-dev preview --source <file> --user` ("Preview a page"). Its CSS reads the
live theme's tokens, and the `playground` package's elements
(`<root>/skills/leaf/packages/playground/guidance/author.md`) hold the controls and
presets, the candidates' preview, and an output saying what to build.

Where the subject exists and the candidates are to be built, implement each in the
runtime and theme that own the surface and show it through a shipped example or
fixture. An unbuilt sketch is page-local markup derived from the current surface's
controls, copy, and styling, shown beside that surface as the baseline, which a live
`lf-sample` embeds operable (`skills/leaf/references/page-authoring.md`).

## Prove and hand off a visible change

Re-vendor before trusting a browser result after a runtime, theme, registry, or widget
change. A green suite doesn't judge how a page looks: run `/ui-sweep` or look at a
composed page, at a representative desktop viewport (`skills/leaf/assets/AGENTS.md`,
"Layout and motion"). Capture fixed chrome by cropping a viewport capture, since a
Playwright screenshot of an element taller than the viewport draws fixed overlays in
the wrong place.

To ask a page where an element sits, what style it computes, or what holds focus after
a key, run `uv run leaf-dev probe` (`dev/AGENTS.md`) rather than writing a Playwright
script.

`uv run leaf-dev stills` crops each state in its catalogue that changed between the
merge base and HEAD into a before/after pair. It compares commits, so commit first.
Where a change reaches a state the catalogue (`STATES`) lacks, such as one a user
reaches by a key, add it rather than driving the state by hand.

The handoff gives each difference a still can show one sentence and a matched
before/after pair, in the reply or as one `lf-shot`; a live preview may accompany the
pair but doesn't replace it. For an interaction-only change, serve both versions
("Compare checkout versions") and hand off the two labeled URLs with the action that
reveals the difference, at the same fragment, viewport, theme, and interaction state.
A preview handed to the user stays running, and its URL carries the fragment of the
block it is about (a titled section's own id).

## Preview a page

`uv run leaf-dev preview <example>` serves a live page at `.tmp/previews/<example>`
that follows source and runtime edits. It runs in the foreground like a dev server, so
run it as a long-running command (`run_in_background` in Claude Code).
`--source <file>` serves any authored HTML file, `--slot <name>` runs another copy,
and `--export` writes one file that opens offline instead.

A plain preview takes no claim, so its presses reach only the page's log; use it for
screenshots and browser checks. `--user` claims the page, at
`.tmp/previews/<example>-user`, so the user's comments reach `leaf wait`, and every
click this session drives there reads as an unanswered user move. So drive only plain
previews, start a `--user` preview from the session the user talks to, and answer the
user's feedback before restarting it, since a restart discards the claim and the moves
it held. Don't idle a preview to quiet the loop: `idle` ends the agent's side of the
page (`skills/leaf/references/page-checkpoints.md`).

### In Codex

1. Start the preview with `--user` as a long-running command. A restarted preview is a
   new page and needs step 3 again.
2. Call `mcp__codex_app__open_in_codex` with the fragment URL as a browser target and
   `placement: "right"`.
3. Run `<root>/bin/leaf codex start <root>/.tmp/previews/<example>-user` so Leaf
   comments return to the current task.
4. Tell the user to select page text or use Leaf's comment affordance for a Leaf
   thread. Codex Annotation mode sends visual comments with their next chat message,
   and the review pane takes feedback on a source line.

## Test the hosted website agent

`uv run --project <root> leaf-dev verify-site local` asks the website agent for one
heading edit through the Python adapter on the host's Codex login, and checks the
reply and the changed page in Chrome. It bypasses the Cloudflare Worker, container
limits, and credential proxy; when a change touches those and `OPENAI_API_KEY` is
exported, run the check through Wrangler's local container:

```bash
npm ci --prefix <root>/worker
npm run build --prefix <root>/worker
uv run --project <root> leaf-dev verify-site wrangler --agent
```

Only the `publish-site` workflow's run against the deployed release reads production.

## Test a terminal Codex task

`uv run --project <root> leaf-dev verify-codex-task` runs a real Codex task through
Leaf's App Server adapter, with this working tree as its plugin. Run it after a change to `codex.py`, `codex_adapter.py`, `hooks.py`,
`hook_carrier.py`, or the claim's turn in `service.py`: the suite scripts App Server,
and only this run shows what Codex itself sends. It spends a few turns on the host's
Codex login, which CI lacks.

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

Use one shared source for a runtime change, or each checkout's copy when the authored
content changed. Run the two previews as separate long-running commands, adding
`--user` to both when their URLs go to the user:

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

Every authored Leaf source is a page: a site page under `docs/`, a shipped example or
fixture, a playground, or a page made for this conversation. Before writing one, read
`<root>/skills/leaf/SKILL.md` completely and follow its authoring, validation, handoff,
and conversation-loop routes, with the checkout launcher and references resolved from
`<root>/skills/leaf/`. To make an existing page run the current checkout, re-vendor it
with the checkout launcher (`<root>/skills/leaf/references/serving-pages.md`), and fix
or report a compatibility refusal rather than falling back to the installed plugin. A
page that explains how a Leaf interface behaves lets the user operate it
(`references/sample-explainers.md`).

## Score a guidance change

Each `evals/<case>/case.yaml` is a moment in a session that `claude plugin eval` hands
a headless Claude Code with this checkout as its only plugin, so the child loads
`leaf:leaf` and reads the references as a real session does. Score a change to
`skills/leaf/` on the cases it bears on:

```bash
uv run leaf-dev guidance-eval [CASE]... [--base REF] [--runs N]
```

It runs both arms at once, the base's guidance (by default the merge base with `main`)
and the working tree's. It passes `--allow-tools Skill Read`: without it, the child's
`dontAsk` mode refuses the skill and the references, every run answers with no
guidance, and the `loads-leaf` grader still passes on the attempt. So every case also
grades that the child read the reference it tests, and a run that fails that check
measured nothing. The grant covers only the leaf skill's base directory, and a
`tool_used` grader counts a refused call too, so its `input_match` names the file's
whole path from `skills/leaf/`.

Cases accumulate, so each later edit, a cut included, is scored against the behaviors
earlier edits needed. To cover a behavior no case covers, first extend an existing case
with a grader, a criterion, or prompt context, and add a case only where none can carry
it; keep what you add whether or not it separated the arms. A case is one prompt with
only the context the behavior needs, and a few graders. The comment above
`schema_version` says where the case came from and what it measured, including whether
it ever separated two wordings; `description` names the clause it pins, and `tags` its
area.

The prompt never states the behavior under test, and ends by asking for the HTML in the
reply, since the child has no page directory. The child can't search the plugin, so it
answers from the references without the registry, and a prompt pointing it at another
file names it from the skill's base directory. Grade a fixed form with a `regex` grader
and a judgment with an `llm` grader whose `criteria` state the passing reading without
requiring particular wording.

A case that states its situation plainly usually passes on both arms, because the
failing session had earlier turns or a competing instruction pulling the other way;
paste those into the prompt, and replay the session when the rule loses only to a long
context. `notes/usability-eval/harness.py` runs cases that need a page directory and
`leaf`. No grader has been checked against a person's judgment, so a pass is weak
evidence.

## Refresh the public catalog stills

When a change adds or removes a worked example or changes its first viewport, run
`wt refresh-previews` from the repository root on macOS once the examples are ready,
and again after integrating `main` or a later fix that changes a first viewport. It
pushes the stills to `max-sixty/leaf-assets` and moves the pin in `leaf-assets.json`
and the README's image URLs; that push is part of the authorized change.
`uv run leaf-dev record-demo` does the same for the README's recording and stills and
the site's card. In a new checkout run `wt setup` first; if Worktrunk asks to approve
the project commands, ask the user to run `wt config approvals add`.

## Land a change

A red gate is the branch's to fix. A pull request's `test` job and the local pre-merge
`tests` run the broad selection, which main passes, plus the nightly-marked tests in
the test files the change touches. The rest of the nightly suite runs once main moves,
and `tend-ci-fix` answers its failures. `wt merge` checks the rebased tree and lands
it; `✗ Can't push to local main branch` is a fast-forward failure.

Installed sessions load host caches, not the checkout. Claude Code picks up a push on
its marketplace sweep. The post-merge hook refreshes an installed Codex plugin; after a
merge that skipped hooks, run `codex plugin marketplace upgrade leaf`.
